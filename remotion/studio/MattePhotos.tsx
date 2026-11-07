import React from 'react';
import {AbsoluteFill, Easing, Img, interpolate, Loop, OffthreadVideo, Sequence, staticFile, useCurrentFrame, useVideoConfig} from 'remotion';
import {Audio} from '@remotion/media';

// Port of remotion/src/matte-photos (BaronMattePhotos). The element length sets the time per photo;
// the transition stays 12 frames, alternating up/left, with paper, scratches and film overlay.
export type Photo = {source:string; face?:number[]; contain?:boolean; zoom?:number; width?:number; height?:number};
export type PhotoElement = {photos:Photo[]; sfx?:boolean};
const W=1080,H=1920,TRANSITION=12;
const ease=Easing.bezier(.4,0,.2,1);
const clamp={extrapolateLeft:'clamp',extrapolateRight:'clamp'} as const;
const offset=(progress:number,axis:'up'|'left',enter:boolean)=>{
  const distance=enter?1-ease(progress):-ease(progress);
  return axis==='up'?`translateY(${distance*H}px)`:`translateX(${distance*W}px)`;
};
const direction=(boundary:number)=>boundary%2===0?'up':'left';

const Cue:React.FC<{file:string;from:number;frames:number;volume:number}>=({file,from,frames,volume})=>
  <Sequence from={Math.round(from)} durationInFrames={Math.max(1,Math.round(frames))}>
    <Audio src={staticFile(file)} volume={f=>volume*interpolate(f,[0,1,Math.max(2,frames)],[0,1,0],clamp)}/>
  </Sequence>;

export const MattePhotos:React.FC<{element:PhotoElement;length:number}>=({element,length})=>{
  const frame=useCurrentFrame(); const {fps}=useVideoConfig();
  const photos=element.photos; const n=photos.length;
  const step=(length-TRANSITION)/n, exposure=step+TRANSITION;
  const cues:{file:string;from:number;frames:number;volume:number}[]=[];
  if(element.sfx!==false){
    // Speech ducking .72 from the original template is folded into the volumes.
    for(let i=0;i<n-1;i++) cues.push({file:'matte/dragon-whoosh-short.wav',from:(i+1)*step-2,frames:.7*fps,volume:.14*.72});
    for(let i=0;i<n;i++){
      const start=i===0?0:i*step-2+21, end=i===n-1?length:(i+1)*step-2;
      for(let t=start;t<end;t+=11) cues.push({file:'matte/dragon-camera.wav',from:t,frames:Math.min(11,end-t),volume:.12*.72});
    }
  }
  return <AbsoluteFill style={{background:'#121212',overflow:'hidden',isolation:'isolate'}}>
    {cues.map((c,i)=><Cue key={i} {...c}/>)}
    {photos.map((photo,i)=>{
      const t=frame-i*step; const last=i===n-1;
      if(t<0||(!last&&t>=exposure)) return null;
      const face=photo.face??[.5,.5], contain=photo.contain??true, zoom=photo.zoom??1.06;
      const ratio=(photo.width||1440)/(photo.height||1800);
      const factor=contain?Math.min(W/ratio,H):Math.max(W/ratio,H);
      const iw=factor*ratio, ih=factor;
      const left=contain?(W-iw)/2:Math.max(W-iw,Math.min(0,W/2-face[0]*iw));
      const top=contain?(H-ih)/2:Math.max(H-ih,Math.min(0,H*.35-face[1]*ih));
      const visible=last?length-i*step:exposure;
      const scale=1+(zoom-1)*t/Math.max(1,visible-1);
      let transform='none';
      if(i>0&&t<TRANSITION) transform=offset(t/TRANSITION,direction(i-1),true);
      if(!last&&t>=step) transform=offset((t-step)/TRANSITION,direction(i),false);
      const src=staticFile(photo.source);
      return <AbsoluteFill key={`${i}-${photo.source}`} style={{overflow:'hidden',transform,background:'#121212'}}>
        {contain&&<Img src={src} style={{width:W,height:H,objectFit:'cover',filter:'blur(28px) brightness(.48)',transform:'scale(1.1)'}}/>}
        <AbsoluteFill style={{transformOrigin:`${left+face[0]*iw}px ${top+face[1]*ih}px`,transform:`scale(${scale})`}}>
          <Img src={src} style={{position:'absolute',left,top,width:iw,height:ih}}/>
        </AbsoluteFill>
      </AbsoluteFill>;
    })}
    <AbsoluteFill style={{background:'#101014',opacity:.24}}/>
    <AbsoluteFill style={{background:'#858580',opacity:.24}}/>
    <Img src={staticFile('matte/paper.jpg')} style={{position:'absolute',width:W,height:H,objectFit:'cover',mixBlendMode:'multiply',opacity:.62}}/>
    <Img src={staticFile('matte/scratches.jpg')} style={{position:'absolute',width:W,height:H,objectFit:'cover',mixBlendMode:'screen',opacity:.48}}/>
    <AbsoluteFill style={{mixBlendMode:'screen',opacity:.65}}>
      <Loop durationInFrames={150}><OffthreadVideo src={staticFile('matte/element.mov')} muted style={{width:W,height:H,objectFit:'cover',filter:'brightness(2)'}}/></Loop>
    </AbsoluteFill>
  </AbsoluteFill>;
};
