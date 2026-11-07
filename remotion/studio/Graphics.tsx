import React from 'react';
import {AbsoluteFill, Easing, interpolate, Sequence, staticFile, useCurrentFrame, useVideoConfig} from 'remotion';
import {Audio} from '@remotion/media';
import {geoGraticule10, geoInterpolate, geoOrthographic, geoPath} from 'd3-geo';
import {feature, mesh} from 'topojson-client';
import landTopo from 'world-atlas/land-50m.json';
import countriesTopo from 'world-atlas/countries-50m.json';

// Natural Earth 1:50m (public domain) via world-atlas; parsed once per bundle.
const LAND=feature(landTopo as any,(landTopo as any).objects.land) as any;
const BORDERS=mesh(countriesTopo as any,(countriesTopo as any).objects.countries,(a:any,b:any)=>a!==b) as any;
const GRATICULE=geoGraticule10();

// Graphics in style A (dark, sporty, gradient glow like the reference counter). Data comes from the plan;
// `land_at` is the reel time when the count must reach its final value (the spoken word).
type Place = {name:string; lat:number; lon:number};
export type GraphicData = {
  value?:number; from?:number|Place; of?:number; label?:string; suffix?:string;
  city?:string; country?:string; lat?:number; lon?:number; date?:string;
  land_at?:number;
};
export type GraphicElement = {variant:string; start:number; end:number; data:GraphicData};

const GRADIENT='linear-gradient(135deg,#E3165E 0%,#9B2BD6 50%,#3B5BFF 100%)';
const clamp={extrapolateLeft:'clamp',extrapolateRight:'clamp'} as const;
const ease=Easing.out(Easing.cubic);
// Floor, not round: the final value appears exactly on land_at, not a few frames before the word.
const tally=(from:number,to:number,p:number)=>p>=1?to:Math.floor(from+(to-from)*p);

const Backdrop:React.FC<{frame:number;fps:number}>=({frame,fps})=>{
  // Two slow colour glows on near-black, so the frame never looks like a flat slide.
  const t=frame/fps;
  return <AbsoluteFill style={{background:'#050508'}}>
    <div style={{position:'absolute',left:540-520+Math.sin(t*.6)*60,top:700-520,width:1040,height:1040,borderRadius:'50%',background:'radial-gradient(circle,rgba(227,22,94,.30) 0%,rgba(227,22,94,0) 65%)'}}/>
    <div style={{position:'absolute',left:540-420+Math.cos(t*.5)*80,top:900-420,width:840,height:840,borderRadius:'50%',background:'radial-gradient(circle,rgba(59,91,255,.30) 0%,rgba(59,91,255,0) 65%)'}}/>
  </AbsoluteFill>;
};

const gradientText=(size:number):React.CSSProperties=>({fontSize:size,fontWeight:800,letterSpacing:'-0.04em',lineHeight:1,
  backgroundImage:GRADIENT,WebkitBackgroundClip:'text',backgroundClip:'text',color:'transparent',
  filter:'drop-shadow(0 0 28px rgba(155,43,214,.55)) drop-shadow(0 0 60px rgba(59,91,255,.35))'});

// Progress 0→1 of the count, finishing on land_at (reel seconds), started 0.3 s after the graphic appears.
const landing=(e:GraphicElement)=>Math.max(e.start+.8,Math.min(e.end-.2,e.data.land_at??e.start+(e.end-e.start)*.55));
const progress=(e:GraphicElement,frame:number,fps:number)=>interpolate(frame,[.3*fps,(landing(e)-e.start)*fps],[0,1],{...clamp,easing:ease});
const useCount=(e:GraphicElement)=>{
  const frame=useCurrentFrame(); const {fps}=useVideoConfig();
  const enter=interpolate(frame,[0,8],[0,1],{...clamp,easing:ease});
  return {frame,fps,p:progress(e,frame,fps),enter,landFrame:(landing(e)-e.start)*fps};
};

// Steady ticks while the number runs, like the reference counter (about 10 per second, every 3 frames),
// the last one louder on land_at.
const TICK_VOLUME=.22, TICK_EVERY=3;
const Ticks:React.FC<{e:GraphicElement;fps:number}>=({e,fps})=>{
  const first=Math.round(.3*fps), land=Math.round((landing(e)-e.start)*fps);
  const frames:number[]=[];
  for(let f=first;f<=land-TICK_EVERY+1;f+=TICK_EVERY) frames.push(f);
  return <>{[...frames,land].map((f,i,all)=><Sequence key={f} from={f} durationInFrames={4}>
    <Audio src={staticFile('graphics/tick.wav')} volume={TICK_VOLUME*(i===all.length-1?1.5:1)}/>
  </Sequence>)}</>;
};

const Counter:React.FC<{e:GraphicElement;font:string}>=({e,font})=>{
  const {frame,fps,p,enter,landFrame}=useCount(e); const d=e.data;
  const value=tally((d.from as number)??0,d.value??0,p);
  return <AbsoluteFill style={{fontFamily:font}}>
    <Backdrop frame={frame} fps={fps}/>
    <Ticks e={e} fps={fps}/>
    <div style={{position:'absolute',top:520,left:0,right:0,display:'flex',flexDirection:'column',alignItems:'center',opacity:enter,transform:`scale(${.92+.08*enter})`}}>
      <div style={{display:'flex',alignItems:'baseline',gap:24}}>
        <span style={{...gradientText(380),fontVariantNumeric:'tabular-nums'}}>{value.toLocaleString('pl-PL')}{d.suffix??''}</span>
        {d.of!==undefined&&<span style={{fontSize:150,fontWeight:700,letterSpacing:'-0.04em',color:'rgba(255,255,255,.45)',opacity:interpolate(frame,[landFrame,landFrame+8],[0,1],clamp)}}>/{d.of}</span>}
      </div>
      {d.label&&<div style={{marginTop:36,fontSize:54,fontWeight:700,letterSpacing:'0.12em',color:'#fff',textTransform:'uppercase'}}>{d.label}</div>}
    </div>
  </AbsoluteFill>;
};

// Globe: spins about 150° to the city (or flies the arc from `from` when given), drops the pin, zooms in
// to country level and names the place above the globe, clear of the captions.
// Timings are for a 4.3 s graphic and shrink proportionally for shorter ones (never below 3 s by validation).
const Globe:React.FC<{e:GraphicElement;font:string}>=({e,font})=>{
  const frame=useCurrentFrame(); const {fps}=useVideoConfig(); const d=e.data;
  const k=Math.min(1,(e.end-e.start-.4)/3.9); const t=frame/fps/k;
  const city:[number,number]=[d.lon??0,d.lat??0];
  const from=(d.from&&typeof d.from==='object')?d.from:null;
  const turn=interpolate(t,[0,1.6],[0,1],{...clamp,easing:Easing.inOut(Easing.cubic)});
  const centre:[number,number]=from?geoInterpolate([from.lon,from.lat],city)(turn) as [number,number]:[city[0]-150*(1-turn),city[1]*turn];
  const zoom=interpolate(t,[1.8,3.0],[1,10.1],{...clamp,easing:Easing.inOut(Easing.cubic)});
  const R=380*zoom, cx=540, cy=860;
  const projection=geoOrthographic().scale(R).translate([cx,cy]).rotate([-centre[0],-centre[1]]).clipAngle(90);
  const path=geoPath(projection);
  const arcDone=from?interpolate(t,[.2,1.6],[0,1],clamp):0;
  const arc=from?{type:'LineString',coordinates:Array.from({length:41},(_,i)=>geoInterpolate([from.lon,from.lat],city)(i/40*arcDone))} as any:null;
  const pinIn=interpolate(t,[1.5,1.85],[0,1],{...clamp,easing:Easing.out(Easing.back(2))});
  const pulse=(t*1.4)%1;
  const pin=projection(city)??[cx,cy];
  const label1=interpolate(t,[2.2,2.6],[0,1],clamp), label2=interpolate(t,[2.5,2.9],[0,1],clamp);
  const enter=interpolate(frame,[0,8],[0,1],{...clamp,easing:ease});
  return <AbsoluteFill style={{fontFamily:font}}>
    <Backdrop frame={frame} fps={fps}/>
    <svg width={1080} height={1920} style={{position:'absolute',opacity:enter}}>
      <defs><clipPath id="globe-clip"><circle cx={cx} cy={cy} r={R}/></clipPath></defs>
      <circle cx={cx} cy={cy} r={R} fill="#0b1030" stroke="rgba(91,116,255,.55)" strokeWidth={3}/>
      <g clipPath="url(#globe-clip)">
        <path d={path(GRATICULE as any)??''} fill="none" stroke="rgba(255,255,255,.07)" strokeWidth={1.5}/>
        <path d={path(LAND)??''} fill="#1c2863" stroke="#5b74ff" strokeWidth={1.6}/>
        <path d={path(BORDERS)??''} fill="none" stroke="rgba(140,160,255,.5)" strokeWidth={1.4}/>
        {arc&&<path d={path(arc)??''} fill="none" stroke="#E3165E" strokeWidth={5} strokeLinecap="round" strokeDasharray="2 14" opacity={interpolate(t,[2.4,2.8],[1,0],clamp)}/>}
      </g>
      <g transform={`translate(${pin[0]},${pin[1]}) scale(${pinIn})`}>
        <circle r={24+50*pulse} fill="none" stroke="#E3165E" strokeWidth={4} opacity={1-pulse}/>
        <circle r={20} fill="#E3165E" stroke="#fff" strokeWidth={5}/>
      </g>
    </svg>
    <div style={{position:'absolute',top:230,left:0,right:0,textAlign:'center',textShadow:'0 4px 24px rgba(0,0,0,.8)'}}>
      {d.country&&<div style={{opacity:label1,fontSize:46,fontWeight:700,letterSpacing:'0.14em',color:'rgba(255,255,255,.85)',textTransform:'uppercase'}}>{d.country}</div>}
      <div style={{opacity:label2,marginTop:8,fontSize:96,fontWeight:800,letterSpacing:'-0.03em',color:'#fff'}}>{d.city}</div>
      {d.date&&<div style={{opacity:label2,marginTop:6,fontSize:46,fontWeight:700,color:'#E3165E'}}>{d.date}</div>}
    </div>
  </AbsoluteFill>;
};

export const Graphic:React.FC<{element:GraphicElement;font:string}>=({element,font})=>{
  if(element.variant==='counter') return <Counter e={element} font={font}/>;
  if(element.variant==='globe') return <Globe e={element} font={font}/>;
  return null;
};
