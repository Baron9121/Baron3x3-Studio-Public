from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from mcp.server.fastmcp import FastMCP
from scripts.resolve_free.pipeline import search_library, prepare_reel, queue_plan, supersede_pending, status, render_captions, queue_caption_overlay, BASE
server=FastMCP('Baron3x3 Resolve Free')
@server.tool()
def library_search(query:str,limit:int=6)->list[dict]:
    """Search existing Baron3x3.md without reanalyzing the library or using paid API."""
    return search_library(query,limit)
@server.tool()
def prepare_edit(source_file:str,prompt:str,library_query:str='',budget_usd:float=0)->dict:
    """Local Whisper + Gemini video analysis via OpenRouter. Requires explicit user budget for analysis. Returns a plan, does not render. Max source duration 180 seconds."""
    return prepare_reel(source_file,prompt,library_query,budget_usd)
@server.tool()
def queue_edit(plan:dict)->dict:
    """Validate edit_plan and prepare internal Resolve Free script when user requested montage. awaiting_resolve NEVER means rendered. User runs Workspace > Scripts > Baron3x3 - wykonaj montaz."""
    return queue_plan(plan)
@server.tool()
def supersede_pending_edit(reason:str)->dict:
    """Archive an unexecuted queued plan before a user-requested revision. Never replaces a plan already run in DaVinci."""
    return supersede_pending(reason)
@server.tool()
def render_status(name:str)->dict:
    """Verify actual render dimensions, frame count, audio presence and full decode. Does not assess editorial quality."""
    return status(name)
@server.tool()
def add_captions(name:str)->dict:
    """Burn verified Polish green-word captions from the cached Whisper transcript onto a Resolve render. No paid API call."""
    return render_captions(name)
@server.tool()
def add_captions_to_timeline(name:str)->dict:
    """Prepare the already-rendered caption alpha layer for V3 in the existing Resolve timeline."""
    return queue_caption_overlay(name)
@server.tool()
def capabilities()->dict:
    """Report tested capabilities and Free manual handoff."""
    return {'backend':'Resolve Free internal Lua + post-render captions','externalAPI':False,'manualStepRequired':True,'tested':['import','1080x1920','cuts','V2 B-roll','static zoom','A1 audio','MP4 H264 AAC render','Whisper-timed green-word captions'],'limitations':['no native Resolve caption-track API','no animated zoom','no automatic editorial QA','max source and timeline 180 seconds'],'index':'assets/library/Baron3x3/Baron3x3.md','pending':str(BASE/'pending.json')}
if __name__=='__main__': server.run(transport='stdio')
