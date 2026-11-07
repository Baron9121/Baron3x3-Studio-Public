import {SoundEffects} from '../SoundEffects';
import React from 'react';
import {AbsoluteFill,Img,staticFile,useCurrentFrame,Easing,OffthreadVideo,Loop} from 'remotion';
const W=1080,H=1920,EXPOSURE=60,TRANSITION=12,STEP=EXPOSURE-TRANSITION;
export const durationFor=(n:number)=>{if(!Number.isInteger(n)||n<1)throw Error('Dodaj przynajmniej jedno zdjęcie');return EXPOSURE+(n-1)*STEP;};
// Coordinates in original images; each supplied photo has its own face anchor.
const profiles=[
 {face:[.49,.53],contain:false,zoom:1.15},
 {face:[.44,.23],contain:false,zoom:1.08},
 {face:[.47,.27],contain:true,zoom:1.06},
 {face:[.64,.31],contain:true,zoom:1.06},
 {face:[.50,.15],contain:false,zoom:1.10},
];
const ease=Easing.bezier(.4,0,.2,1);
const direction=(boundary:number)=>boundary%2===0?'up':'left';
const offset=(progress:number,axis:string,enter:boolean)=>{
 const distance=enter?1-ease(progress):-ease(progress);
 return axis==='up'?`translateY(${distance*H}px)`:`translateX(${distance*W}px)`;
};
export type PhotoProfile={face:number[];contain:boolean;zoom:number;width?:number;height?:number};
export const InstagramStories:React.FC<{photos:string[];photoProfiles?:PhotoProfile[]}>=({photos,photoProfiles})=>{
 const frame=useCurrentFrame();
 return <AbsoluteFill style={{background:'#121212',overflow:'hidden',isolation:'isolate'}}>
 <SoundEffects cues={[
 ...photos.slice(1).map((_,i)=>({id:`matte-whoosh-${i}`,type:'dragon-whoosh' as const,publicFile:'matte-photos/sfx/dragon-whoosh-short.wav',timelineStartMs:((i+1)*STEP-2)/30*1000,volume:.14,speechDucking:.72})),
 ...photos.flatMap((_,i)=>{
 const start=i===0?0:i*STEP-2+21;
 const end=i===photos.length-1?durationFor(photos.length):(i+1)*STEP-2;
 return Array.from({length:Math.max(0,Math.ceil((end-start)/11))},(_,j)=>({id:`matte-camera-${i}-${j}`,type:'dragon-camera' as const,publicFile:'matte-photos/sfx/dragon-camera.wav',timelineStartMs:(start+j*11)/30*1000,durationMs:Math.min(11,end-start-j*11)/30*1000,volume:.12,speechDucking:.72}));
 })
 ]}/>

 {photos.map((src,i)=>{
  const t=frame-i*STEP;if(t<0||t>=EXPOSURE)return null;
  const p:PhotoProfile=photoProfiles?.[i]||{face:[.5,.5],contain:true,zoom:1};
  const ratio=(p.width||1440)/(p.height||1800);
  const factor=p.contain?Math.min(W/ratio,H):Math.max(W/ratio,H);
  const iw=factor*ratio,ih=factor;
  const left=p.contain?(W-iw)/2:Math.max(W-iw,Math.min(0,W/2-p.face[0]*iw));
  const top=p.contain?(H-ih)/2:Math.max(H-ih,Math.min(0,H*.35-p.face[1]*ih));
  const scale=1+(p.zoom-1)*t/(EXPOSURE-1);
  let transform='none';
  if(i>0&&t<TRANSITION)transform=offset(t/TRANSITION,direction(i-1),true);
  if(i<photos.length-1&&t>=STEP)transform=offset((t-STEP)/TRANSITION,direction(i),false);
  return <AbsoluteFill key={`${i}-${src}`} style={{overflow:'hidden',transform,background:'#121212'}}>
   {p.contain&&<Img src={staticFile(src)} style={{width:W,height:H,objectFit:'cover',filter:'blur(28px) brightness(.48)',transform:'scale(1.1)'}}/>}
   <AbsoluteFill style={{transformOrigin:`${left+p.face[0]*iw}px ${top+p.face[1]*ih}px`,transform:`scale(${scale})`}}>
    <Img src={staticFile(src)} style={{position:'absolute',left,top,width:iw,height:ih}}/>
   </AbsoluteFill>
  </AbsoluteFill>;
 })}
 <AbsoluteFill style={{background:'#101014',opacity:.24,pointerEvents:'none'}}/>
 <AbsoluteFill style={{background:'#858580',opacity:.24,pointerEvents:'none'}}/>
 <Img src={staticFile('matte-photos/overlays/paper.jpg')} style={{position:'absolute',width:W,height:H,objectFit:'cover',mixBlendMode:'multiply',opacity:.62,pointerEvents:'none'}}/>
 <Img src={staticFile('matte-photos/overlays/scratches.jpg')} style={{position:'absolute',width:W,height:H,objectFit:'cover',mixBlendMode:'screen',opacity:.48,pointerEvents:'none'}}/>
 <AbsoluteFill style={{mixBlendMode:'screen',opacity:.65,pointerEvents:'none'}}>
 <Loop durationInFrames={150}><OffthreadVideo src={staticFile('matte-photos/overlays/element.mov')} muted style={{width:W,height:H,objectFit:'cover',filter:'brightness(2)'}}/></Loop>
 </AbsoluteFill>
 </AbsoluteFill>;
};
