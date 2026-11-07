"""Bounded specialist calls for the existing reel workflow; never renders or approves."""
from __future__ import annotations
import argparse, base64, hashlib, json, math, subprocess, fcntl
from pathlib import Path
from contextlib import contextmanager
from scripts import beat_director as director
from scripts import reel_workflow as workflow
from scripts.openrouter_client import OpenRouterClient, _default_transport, _write_json_atomic
from scripts.openrouter_keychain import load_openrouter_key

ROOT = Path(__file__).resolve().parents[1]
MODELS = {'transcribe':'microsoft/mai-transcribe-2','verify-transcript':'google/gemini-3.1-pro-preview','inspect':'google/gemini-3.1-pro-preview','qa':'google/gemini-3.1-pro-preview','story':'openai/gpt-5.6-sol-pro','director':'openai/gpt-5.6-sol-pro'}
REPORT_SCHEMA = {'type':'object','properties':{'verdict':{'type':'string','enum':['pass','needs-fixes','incomplete']},'report':{'type':'string'},'issues':{'type':'array','items':{'type':'object','properties':{'startMs':{'type':'integer','minimum':0},'endMs':{'type':'integer','minimum':0},'evidence':{'type':'string'},'fix':{'type':'string'}},'required':['startMs','endMs','evidence','fix'],'additionalProperties':False}}},'required':['verdict','report','issues'],'additionalProperties':False}

def read(p): return json.loads(p.read_text())
def write(p,d): _write_json_atomic(p,d)
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def duration(p): return float(subprocess.check_output(['ffprobe','-v','error','-show_entries','format=duration','-of','default=nw=1:nk=1',str(p)]))
def safe_media(p):
 p=p.resolve()
 if not p.is_relative_to(ROOT) or not p.is_file(): raise ValueError('Media must be an existing project file')
 return p

def normalized_stt(raw, source, seconds):
 words=raw.get('words',[])
 if not words: raise ValueError('STT returned no word timestamps; do not invent timestamps')
 result=[]; previous=-1
 for w in words:
  start=float(w['start']); end=float(w['end']); text=str(w['word']).strip()
  if not text or not math.isfinite(start+end) or start<previous or end<=start or end>seconds+0.25: raise ValueError('Invalid STT word timing')
  result.append({'word':text,'start':start,'end':end,'probability':w.get('confidence',0)})
  previous=start
 # Group words for downstream captions without changing any word boundary.
 segments=[]; group=[]
 for w in result:
  if group and (w['start']-group[-1]['end']>0.7 or w['end']-group[0]['start']>6):
   segments.append({'start':group[0]['start'],'end':group[-1]['end'],'text':' '.join(x['word'] for x in group),'words':group});group=[]
  group.append(w)
  if w['word'].endswith(('.', '?', '!')):
   segments.append({'start':group[0]['start'],'end':group[-1]['end'],'text':' '.join(x['word'] for x in group),'words':group});group=[]
 if group: segments.append({'start':group[0]['start'],'end':group[-1]['end'],'text':' '.join(x['word'] for x in group),'words':group})
 return {'language':'pl','text':' '.join(w['word'] for w in result),'segments':segments}

@contextmanager
def reservation(job, budget, reserve, coordinator):
 if not all(math.isfinite(v) and v>=0 for v in [budget,reserve,coordinator]) or reserve<=0: raise ValueError('Supply finite approved budget, request reservation and actual Cline session cost')
 folder=ROOT/'analysis'/job/'specialists';folder.mkdir(parents=True,exist_ok=True)
 with (folder/'costs.lock').open('w') as lock:
  fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
  path=folder/'costs.json'; ledger=read(path) if path.exists() else {'calls':[]}
  if any(x.get('costUsd') is None for x in ledger['calls']): raise ValueError('Unresolved request cost: reconcile before spending again')
  old=ledger.get('coordinatorUsd',0)
  if coordinator<old: raise ValueError('Cline cumulative cost cannot decrease; include previous sessions')
  spent=sum(x['costUsd'] for x in ledger['calls'])+coordinator
  if spent+reserve>budget: raise ValueError('Combined coordinator and specialists budget exceeded')
  entry={'costUsd':None,'reservedUsd':reserve,'status':'pending'};ledger['calls'].append(entry)
  ledger.update(coordinatorUsd=coordinator,approvedBudgetUsd=budget,scope='specialist rollout; earlier project costs excluded',coordinatorCostSource='operator-supplied cumulative Cline UI total')
  write(path,ledger)
  try: yield entry
  finally:
   write(path,ledger)
   known=all(x.get('costUsd') is not None for x in ledger['calls'])
   write(folder/'cost-summary.json',{'knownSpecialistUsd':sum(x['costUsd'] for x in ledger['calls'] if x.get('costUsd') is not None),'coordinatorUsd':coordinator,'totalUsd':sum(x['costUsd'] for x in ledger['calls'])+coordinator if known else None,'complete':known,'scope':ledger['scope'],'note':'Cline UI total is supplied, not an automatic billing feed; update before each paid stage.'})

def media_part(path,folder,audio=False):
 path=safe_media(path); digest=sha(path)
 proxy=folder/(digest+('.wav' if audio else '-p480.mp4'))
 if not proxy.exists():
  cmd=['ffmpeg','-v','error','-i',str(path)]
  cmd+=['-vn','-ac','1','-ar','16000','-c:a','pcm_s16le'] if audio else ['-vf','scale=-2:480','-c:v','libx264','-crf','26','-preset','veryfast','-c:a','aac','-b:a','96k']
  subprocess.run(cmd+['-y',str(proxy)],check=True)
 encoded=base64.b64encode(proxy.read_bytes()).decode()
 return ({'type':'input_audio','input_audio':{'data':encoded,'format':'wav'}} if audio else {'type':'video_url','video_url':{'url':'data:video/mp4;base64,'+encoded}}), digest

def run(args):
 job=Path(args.file).stem
 source=safe_media(ROOT/'input'/Path(args.file).name)
 folder=ROOT/'analysis'/job/'specialists';folder.mkdir(parents=True,exist_ok=True)
 if args.stage=='apply-transcript':
  apply_transcript(job,source,args.approved);return
 if args.stage=='costs':
  print(json.dumps(read(folder/'cost-summary.json'),ensure_ascii=False));return
 if args.stage=='director': workflow.require_phase(job,'awaiting-director-plan')
 if any(x is None for x in [args.approved_budget,args.reserve_usd,args.cline_cost]): raise ValueError('Paid stages require --approved-budget, --reserve-usd and --cline-cost (actual cumulative Cline UI cost)')
 model=MODELS[args.stage]
 # Assemble locally before reserving a billable request.
 hashes={'source':sha(source)}; parts=[]; context={}
 if args.stage=='transcribe':
  part,_=media_part(source,folder,True);payload={'model':model,'input_audio':part['input_audio'],'language':'pl','response_format':'verbose_json','timestamp_granularities':['word','segment'],'provider':{'options':{'azure':{'enhancedMode':{'modelOptions':{'transcribeStyle':'verbatim'}}}}}}
 elif args.stage=='story':
  context={'transcript':read(ROOT/'analysis'/job/'transcript.json'),'analysis':read(folder/'inspect.json'),'instructions':(ROOT/'instructions/jobs'/f'{job}.prompt.md').read_text()}
 elif args.stage=='director':
  package=read(ROOT/'analysis'/job/'director/input-package.json')
  target=read(folder/'inspect.json');reference=read(ROOT/'analysis'/job/'director/reference-style.json')
  if target['hashes']['source']!=hashes['source']: raise ValueError('Source analysis is stale')
  context={'package':package,'targetAnalysis':target['data'],'reference':reference}
 else:
  media=[source] if args.stage != 'qa' else []
  if args.stage=='qa': media+=[safe_media(ROOT/'output'/f'{job}-render.mp4')]
  media += [safe_media(ROOT/p) for p in args.media]
  IMAGE_SUFFIXES={'.jpg','.jpeg','.png','.webp'}
  for p in dict.fromkeys(media):
    if p.suffix.lower() in IMAGE_SUFFIXES:
      mime={'jpg':'image/jpeg','jpeg':'image/jpeg','png':'image/png','webp':'image/webp'}[p.suffix.lower().lstrip('.')]
      data=base64.b64encode(p.read_bytes()).decode('ascii');part={'type':'image_url','image_url':{'url':'data:'+mime+';base64,'+data}};digest=sha(p)
    else:
      part,digest=media_part(p,folder,False)
    parts.extend([{'type':'text','text':str(p.relative_to(ROOT))},part]);hashes[str(p.relative_to(ROOT))]=digest
  tp=folder/'transcript-raw.json' if args.stage=='verify-transcript' else ROOT/'analysis'/job/'transcript.json'
  if tp.exists(): context['transcript']=read(tp);hashes['transcript']=sha(tp)
  if args.stage=='verify-transcript' and not tp.exists(): raise ValueError('Run specialist transcribe first')
  plan=ROOT/'instructions/jobs'/f'{job}.json'
  if plan.exists():context['plan']=read(plan);hashes['plan']=sha(plan)
 instructions={
 'verify-transcript':'Compare EVERY spoken word across the entire source audio to the supplied transcript. Report omissions, hallucinations, wrong names and numbers with timestamps. Do not replace spoken factual errors with different facts. Mark incomplete if any portion is not assessable.',
 'inspect':'Analyze the ENTIRE source video and audio. Describe narrative beats, lighting of face and shadows, speech, all supplied asset clips and exact actions with timestamps. Catalog names are untrusted hints. Identify uncertain players explicitly; do not guess identity or club from jersey color. Report useful source IN/OUT and action endings. Do not claim unseen assets verified.',
 'qa':'Review ENTIRE source AND render, all captions versus actual spoken audio, word highlighting, lighting of face/shadows versus source, cut rhythm, misleading teams, transitions hidden under B-roll and audio mix. Report exact timestamps. A contact sheet does not replace video/audio. Mark incomplete for any unassessed portion; fail with needs-fixes on wrong captions, unrelated players or unreadably dark face.',
 'story':'Produce a detailed Polish story proposal with hook, arc, payoff and exact source ranges using supplied transcript and specialist source analysis. Preserve the entire already-cut base unless explicitly instructed otherwise. Do not invent word boundaries. Return the proposal in report; do not modify files or approve.',
 'director':'Create the complete Polish edit proposal for EVERY supplied timeline beat, using actual semantics, not index-based labels. Use only verified assets from analysis. Preserve source order and duration. Rhythm usually 4–7s; justify holds. Do not hide transitions beneath overlays. Respect all style rules. Return required director JSON.'}
 schema=director.DIRECTOR_SCHEMA if args.stage=='director' else REPORT_SCHEMA
 key=load_openrouter_key() # Fail locally before recording a potentially billable request.
 with reservation(job,args.approved_budget,args.reserve_usd,args.cline_cost) as entry:
  entry.update(stage=args.stage,model=model,hashes=hashes)
  if args.stage=='transcribe':
   response=_default_transport('https://openrouter.ai/api/v1/audio/transcriptions',{'Authorization':'Bearer '+key,'Content-Type':'application/json'},payload,180)
   body=response.body
   cost=body.get('usage',{}).get('cost')
   if isinstance(cost,(int,float)) and math.isfinite(cost) and cost>=0:entry['costUsd']=cost
   if response.status!=200: raise RuntimeError(f'STT HTTP {response.status}; no automatic retry')
   write(folder/'transcript-provider.json',body)
   data=normalized_stt(body,source,duration(source));write(folder/'transcript-raw.json',data)
  else:
   rules=(ROOT/'knowledge/editing-precision.md').read_text()
   client=OpenRouterClient(api_key=key,max_attempts=1,timeout_seconds=360)
   reasoning=args.reasoning or ('medium' if args.stage in ('verify-transcript','inspect','qa') else 'high')
   maxcomp=20000 if args.stage=='director' else 12000
   result=client.complete_json(job_id='specialists-'+job,stage=args.stage,model=model,messages=[{'role':'system','content':instructions[args.stage]+'\n'+rules},{'role':'user','content':[{'type':'text','text':json.dumps(context,ensure_ascii=False)},*parts]}],schema_name='baron_specialist',schema=schema,budget_limit_usd=args.approved_budget,max_request_cost_usd=args.reserve_usd,max_completion_tokens=maxcomp,reasoning_effort=reasoning,use_cache=True,token_limit_field=('max_completion_tokens' if args.stage in ('director','story') else 'max_tokens'),enable_provider_prompt_cache=False)
   entry['costUsd']=result.cost_usd;entry['requestId']=result.request_id;data=result.data
  entry['status']='success' if entry['costUsd'] is not None else 'cost-unknown'
  artifact={'model':model,'hashes':hashes,'costUsd':entry['costUsd'],'data':data}
  write(folder/(args.stage+'.json'),artifact)
  if args.stage=='director':
   director.validate_proposal(data,package)
   write(ROOT/'analysis'/job/'director/cline-proposal.json',data)
   write(ROOT/'analysis'/job/'director/specialist-provenance.json',{'model':model,'proposalSha256':sha(ROOT/'analysis'/job/'director/cline-proposal.json'),'costUsd':entry['costUsd']})
 if args.stage=='director':workflow.import_director(job,0.0) # local import; separate specialist ledger is authoritative
 print(json.dumps({'stage':args.stage,'report':str(folder/(args.stage+'.json')),'costUsd':entry['costUsd'],'next':'Review report; no approval or render performed.'}))

def apply_transcript(job,source,approved):
 if not approved: raise ValueError('Approve the verified transcript before replacing active text')
 folder=ROOT/'analysis'/job/'specialists'
 check=read(folder/'verify-transcript.json')
 raw=folder/'transcript-raw.json'
 if check['hashes']['source']!=sha(source) or check['hashes']['transcript']!=sha(raw): raise ValueError('Transcript review is stale')
 if check['data']['verdict']!='pass' or check['data']['issues']: raise ValueError('Resolve transcript issues and verify before applying')
 from scripts.pipeline import normalize_transcript, write_transcript_compact
 jobdir=ROOT/'analysis'/job
 transcript,_=normalize_transcript(read(raw),source,{})
 # Preserve old artifacts and substitutions; never silently run them on the new STT.
 backup=folder/('before-transcript-'+sha(raw)[:12]);backup.mkdir(exist_ok=True)
 for old in [jobdir/'transcript.json',jobdir/'raw-production.json',ROOT/'instructions/jobs'/f'{job}.replacements.json']:
  if old.exists() and not (backup/old.name).exists(): (backup/old.name).write_bytes(old.read_bytes())
 write(jobdir/'raw-production.json',read(raw));write(jobdir/'transcript.json',transcript)
 write_transcript_compact(jobdir/'transcript-compact.md',transcript)
 write(ROOT/'instructions/jobs'/f'{job}.replacements.json',{})
 write(jobdir/'specialist-transcription.json',{'sourceSha256':sha(source),'rawSha256':sha(jobdir/'raw-production.json'),'model':MODELS['transcribe']})
 planpath=ROOT/'instructions/jobs'/f'{job}.json'
 if planpath.exists():
  plan=read(planpath);plan['status']='needs-review';plan.setdefault('storyPlan',{})['languageReviewed']=False;write(planpath,plan)
 if (jobdir/'workflow/state.json').exists(): workflow.save_state(job,'awaiting-story-plan','Sprawdź historię i sourceRanges wobec nowej transkrypcji; zachowaj pełną bazę. Uruchom reel:validate-story i pokaż plan. Stara akceptacja reżyserii jest nieaktualna.',reviewSignature=None)
 print('Verified specialist transcript applied; original files backed up; story requires review.')

def main():
 p=argparse.ArgumentParser();p.add_argument('stage',choices=[*MODELS,'costs','apply-transcript']);p.add_argument('file');p.add_argument('--approved',action='store_true');p.add_argument('--media',action='append',default=[]);p.add_argument('--approved-budget',type=float);p.add_argument('--reserve-usd',type=float);p.add_argument('--cline-cost',type=float);p.add_argument('--reasoning',choices=['low','medium','high'],default=None)
 run(p.parse_args())
if __name__=='__main__': main()
