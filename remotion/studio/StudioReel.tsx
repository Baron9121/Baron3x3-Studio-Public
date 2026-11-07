import React from 'react';
import {AbsoluteFill, CanvasImage, interpolate, Sequence, staticFile, useCurrentFrame, useVideoConfig} from 'remotion';
import {Video, Audio} from '@remotion/media';
import {MattePhotos, type Photo} from './MattePhotos';
import {Graphic, type GraphicData} from './Graphics';

type Word = {text:string; start:number; end:number; highlight?:boolean};
type Element = {id:string; type:string; start:number; end:number; source?:string; kind?:string; source_start?:number; scale_from?:number; scale_to?:number; words?:Word[]; volume?:number; fade_seconds?:number; photos?:Photo[]; sfx?:boolean; variant?:string; data?:GraphicData};
export type StudioPlan = {version:number; project:string; fps:number; width:number; height:number; aroll:{source:string; duration:number; sha256:string}; elements:Element[]};
export type Theme = {green:string; white:string; black:string; fontFamily:string};
export type Props = {plan:StudioPlan; theme:Theme};
const clamp = {extrapolateLeft:'clamp',extrapolateRight:'clamp'} as const;
const src=(path:string)=>staticFile(path);
const fill: React.CSSProperties={width:'100%',height:'100%',objectFit:'cover'};

// Style from reference reels: tight grotesk, centered block, words build up one by one
// (fade + blur in), highlighted words larger with a white glow. Punctuation stays.
const WORD_IN=5;
const Captions: React.FC<{element:Element; theme:Theme}> = ({element,theme}) => {
  const frame=useCurrentFrame(); const {fps}=useVideoConfig();
  const time=element.start+frame/fps;
  return <div style={{position:'absolute',left:64,right:64,top:1230,display:'flex',flexWrap:'wrap',justifyContent:'center',textAlign:'center',alignItems:'baseline',columnGap:'0.2em',rowGap:6,
    fontFamily:theme.fontFamily,fontWeight:700,fontSize:80,lineHeight:1.02,letterSpacing:'-0.045em',color:theme.white}}>
    {(element.words??[]).map((w,i)=>{
      const p=interpolate((time-w.start)*fps,[0,WORD_IN],[0,1],clamp);
      const glow=w.highlight?'0 0 22px rgba(255,255,255,.55), 0 0 6px rgba(255,255,255,.35)':'0 2px 16px rgba(0,0,0,.55)';
      return <span key={i} style={{fontSize:w.highlight?120:undefined,opacity:p,filter:p<1?`blur(${(1-p)*10}px)`:undefined,textShadow:glow}}>{w.text}</span>;
    })}
  </div>;
};
const Layer:React.FC<{element:Element;theme:Theme}>=({element:e,theme})=>{
  const frame=useCurrentFrame(); const {fps}=useVideoConfig(); const length=Math.max(1,Math.round((e.end-e.start)*fps));
  if(e.type==='broll') return <AbsoluteFill style={{overflow:'hidden'}}><AbsoluteFill style={{scale:interpolate(frame,[0,Math.max(1,length-1)],[e.scale_from??1,e.scale_to??1.04],clamp)}}>
    {e.kind==='image'?<CanvasImage src={src(e.source!)} style={fill}/>:<Video src={src(e.source!)} trimBefore={Math.round((e.source_start??0)*fps)} muted style={fill}/>}</AbsoluteFill></AbsoluteFill>;
  if(e.type==='photo') return <MattePhotos element={{photos:e.photos??[],sfx:e.sfx}} length={Math.max(1,Math.round(e.end*fps)-Math.round(e.start*fps))}/>;
  if(e.type==='graphic') return <Graphic element={{variant:e.variant!,start:e.start,end:e.end,data:e.data??{}}} font={theme.fontFamily}/>;
  if(e.type==='caption') return <Captions element={e} theme={theme}/>;
  if(e.type==='music'||e.type==='sfx'){
    const fade=Math.min(length/2,Math.max(1,(e.fade_seconds??.2)*fps));
    const envelope=(f:number)=>Math.max(0,Math.min(1,f/fade,(length-f)/fade));
    return <Audio src={src(e.source!)} trimBefore={Math.round((e.source_start??0)*fps)} volume={f=>(e.volume??.12)*envelope(f)}/>;
  }
  return null;
};
export const StudioReel:React.FC<Props>=({plan,theme})=>{
  const frame=useCurrentFrame(); const time=frame/plan.fps;
  const zoom=plan.elements.find(e=>e.type==='zoom'&&time>=e.start&&time<e.end);
  // Explicit layer order: B-roll, photos, captions; plan order only breaks ties.
  const layers=['broll','photo','graphic','caption','music','sfx'].flatMap(type=>plan.elements.filter(e=>e.type===type));
  return <AbsoluteFill style={{backgroundColor:theme.black,fontFamily:theme.fontFamily,color:theme.white,overflow:'hidden'}}>
    <AbsoluteFill style={{scale:zoom?interpolate(frame,[zoom.start*plan.fps,zoom.end*plan.fps],[zoom.scale_from??1,zoom.scale_to??1],clamp):1}}><Video src={src(plan.aroll.source)} style={fill}/></AbsoluteFill>
    {layers.map(e=><Sequence key={e.id} name={e.id} from={Math.round(e.start*plan.fps)} durationInFrames={Math.max(1,Math.round(e.end*plan.fps)-Math.round(e.start*plan.fps))}><Layer element={e} theme={theme}/></Sequence>)}
  </AbsoluteFill>;
};
