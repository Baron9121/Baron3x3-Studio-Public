"""Regenerate the explicit JSON contract (no runtime code generation)."""
import json
from pathlib import Path
num={'type':'number','minimum':0}
text={'type':'string','minLength':1}
def obj(props, required=None):
    return {'type':'object','additionalProperties':False,'properties':props,'required':required or list(props)}
word=obj({'text':text,'start':num,'end':num,'confidence':{'type':['number','null'],'minimum':0,'maximum':1},'highlight':{'type':'boolean'}}, ['text','start','end'])
base={'id':text,'type':text,'start':num,'end':num,'reason':text}
def element(kind,prefix,extra,required):
    props={**base,'id':{'type':'string','pattern':f'^{prefix}[0-9]{{2,}}$'},'type':{'const':kind},**extra}
    return obj(props,['id','type','start','end',*required])
source={'source':text,'source_start':num}
scale={'type':'number','minimum':1,'maximum':1.5}
elements=[
 element('zoom','Z',{'scale_from':scale,'scale_to':scale},['scale_from','scale_to']),
 element('broll','B',{**source,'kind':{'enum':['video','image']},'scale_from':scale,'scale_to':scale},['source','kind']),
 element('caption','C',{'words':{'type':'array','minItems':1,'maxItems':8,'items':word}},['words']),
 element('photo','P',{'photos':{'type':'array','minItems':1,'maxItems':8,'items':obj({'source':text,
    'face':{'type':'array','minItems':2,'maxItems':2,'items':{'type':'number','minimum':0,'maximum':1}},
    'contain':{'type':'boolean'},'zoom':{'type':'number','minimum':1,'maximum':1.3}},['source'])},'sfx':{'type':'boolean'}},['photos']),
 element('graphic','G',{'variant':{'enum':['counter','globe']},'data':{'type':'object'}},['variant','data']),
 *[element(kind,prefix,{**source,'volume':{'type':'number','minimum':0,'maximum':1},'fade_seconds':{'type':'number','minimum':0,'maximum':5}},['source','volume']) for kind,prefix in [('music','M'),('sfx','S')]]]
schema={'$schema':'https://json-schema.org/draft/2020-12/schema',**obj({
 'version':{'const':1},'project':text,'fps':{'const':30},'width':{'const':1080},'height':{'const':1920},
 'aroll':obj({'source':text,'sha256':{'type':'string','pattern':'^[0-9a-f]{64}$'},'duration':{'type':'number','exclusiveMinimum':0}}),
 'elements':{'type':'array','items':{'oneOf':elements}}})}
Path('schemas/plan.schema.json').write_text(json.dumps(schema,indent=2)+'\n')
