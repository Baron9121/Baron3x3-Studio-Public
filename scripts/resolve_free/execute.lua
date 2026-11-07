-- Runs INSIDE Resolve Free. plan is a validated Lua table generated from edit_plan.json.
local function execute(plan)
  local function check(value, label) if not value then error(label) end return value end
  local already=io.open(plan.report..'.started','r')
  if already then already:close(); error('Already executed: create a new plan version') end
  local report = assert(io.open(plan.report, 'w'))
  local function log(s) report:write(s .. '\n'); report:flush(); print(s) end
  local ok, err = pcall(function()
    local r = check(resolve, 'Run inside Resolve console')
    local pm = r:GetProjectManager()
    local p = check(pm:GetCurrentProject(), 'Open a project first')
    check(p:GetName():match('^Baron3x3%-'), 'Use a dedicated Baron3x3- project')
    check(p:SetSetting('timelineFrameRate', tostring(plan.fps)), 'Frame rate')
    check(p:SetSetting('timelineResolutionWidth', '1080'), 'Width')
    check(p:SetSetting('timelineResolutionHeight', '1920'), 'Height')
    local marker=assert(io.open(plan.report..'.started','w')); marker:write(plan.name); marker:close()
    local pool = p:GetMediaPool()
    local timelineName = plan.timelineName or plan.name
    if plan.replaceTimeline then
      for i=p:GetTimelineCount(),1,-1 do
        local existing=p:GetTimelineByIndex(i)
        if existing and existing:GetName()==timelineName then
          check(p:DeleteTimelines({existing}), 'Delete previous generated timeline')
        end
      end
    end
    local media = {}
    for _, path in ipairs(plan.sources) do
      local imported = check(pool:ImportMedia({path}), 'Import '..path)
      media[path] = check(imported[1], 'Empty import '..path)
    end
    log('PASS import')
    local t = check(pool:CreateEmptyTimeline(timelineName), 'Create unique timeline')
    check(p:SetCurrentTimeline(t), 'Activate timeline')
    check(t:SetStartTimecode('00:00:00:00'), 'Start timecode')
    check(t:GetSetting('timelineResolutionWidth') == '1080', 'Read back width')
    check(t:GetSetting('timelineResolutionHeight') == '1920', 'Read back height')
    log('PASS timeline 1080x1920')
    while t:GetTrackCount('video') < 2 do check(t:AddTrack('video'), 'Add V2') end
    while t:GetTrackCount('audio') < 1 do check(t:AddTrack('audio', 'stereo'), 'Add A1') end
    for _, c in ipairs(plan.clips) do
      local items = check(pool:AppendToTimeline({{mediaPoolItem=media[c.file], startFrame=c.first, endFrame=c.last,
        mediaType=c.mediaType, trackIndex=c.track, recordFrame=c.at + t:GetStartFrame()}}), 'Append clip')
      local item = check(items[1], 'Empty append')
      if c.length then check(math.abs(item:GetDuration()-c.length)<0.1, 'Clip duration mismatch') end
      log('DURATION '..item:GetDuration())
      if c.mediaType == 1 then
        check(item:SetProperty('ZoomX', c.zoom), 'ZoomX')
        check(item:SetProperty('ZoomY', c.zoom), 'ZoomY')
        check(math.abs(item:GetProperty('ZoomX')-c.zoom)<0.001, 'Read back zoom')
      end
      log('PASS clip '..c.mediaType..' track '..c.track..' frame '..c.at)
    end
    if plan.expectedFrames then check(t:GetEndFrame()-t:GetStartFrame()==plan.expectedFrames,'Timeline duration mismatch') end
    check(pm:SaveProject(), 'Save project')
    log('PASS saved timeline '..t:GetName())
    if plan.render == false then
      log('PASS timeline only; render skipped')
      return
    end
    check(p:SetCurrentRenderFormatAndCodec('mp4', 'H264'), 'MP4 H264 codec')
    check(p:SetCurrentRenderMode(1), 'Single clip mode')
    check(p:SetRenderSettings({SelectAllFrames=true,TargetDir=plan.outputDir,CustomName=plan.name,
      ExportVideo=true,ExportAudio=true,FormatWidth=1080,FormatHeight=1920,FrameRate=plan.fps,
      AudioCodec='aac',AudioSampleRate=48000}), 'Render settings')
    local id=check(p:AddRenderJob(), 'Render job')
    log('RENDER_JOB '..id)
    check(p:StartRendering({id}), 'Start render')
    log('RENDER_STARTED '..plan.outputDir..'/'..plan.name..'.mp4')

  end)
  if not ok then log('FAIL '..tostring(err)) end
  report:close()
  if not ok then error(err) end
end
return execute
