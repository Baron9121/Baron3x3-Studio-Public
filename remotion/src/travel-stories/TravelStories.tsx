import React from 'react';
import {AbsoluteFill, Easing, Img, staticFile, useCurrentFrame} from 'remotion';
import rawLayers from './layers.json';
type Value=number|boolean|number[];
type Param={value:Value;keys:{frame:number;value:Value;raw:string[]}[]};
type Layer={track:number;name:string;start:number;end:number;effects:Record<string,Record<string,Param>>};
export type Photo={src:string;fit?:'cover'|'contain'};
export type Props={photos:Photo[]};
const layers=rawLayers as unknown as Layer[];
const scenes=layers.filter(l=>l.name.startsWith('scene_')).sort((a,b)=>a.start-b.start);
const clamp=(v:number)=>Math.max(0,Math.min(1,v));
// Curve values and times are read from Premiere. Temporal easing is an approximation
// because the serialized handle convention is not a documented interchange format.
function sample(p:Param|undefined,f:number,fallback:Value):Value{
 if(!p)return fallback;const k=p.keys;if(!k.length)return p.value;
 if(f<=k[0].frame)return k[0].value;
 if(f>=k[k.length-1].frame)return k[k.length-1].value;
 const i=k.findIndex((v,j)=>j<k.length-1&&f>=v.frame&&f<k[j+1].frame);const a=k[i],b=k[i+1];
 const t=Easing.bezier(.41,0,.48,1)(clamp((f-a.frame)/(b.frame-a.frame)));
 if(Array.isArray(a.value)&&Array.isArray(b.value)){const v=b.value;return a.value.map((n,j)=>n+(v[j]-n)*t);}
 return Number(a.value)+(Number(b.value)-Number(a.value))*t;
}
export const durationFor=(n:number)=>{
 if(!Number.isInteger(n)||n<1)throw Error('Provide at least one photo');
 return n<=7?scenes[n-1].end:450+(n-7)*65;
};
function sceneAt(f:number,n:number){
 if(f>=450)return Math.min(n-1,7+Math.floor((f-450)/65));
 const found=scenes.filter(s=>f>=s.start&&f<s.end).at(-1);return Math.min(n-1,found?Number(found.name.split('_')[1])-1:0);
}
const address=(s:string)=>/^(https?:|data:)/.test(s)?s:staticFile(s);
const PhotoImage:React.FC<{photo:Photo;scale?:number;x?:number;y?:number}>=({photo,scale=1,x=0,y=0})=><AbsoluteFill style={{scale,translate:`${x}px ${y}px`,background:'#180a0e'}}>
 {photo.fit==='contain'&&<Img src={address(photo.src)} style={{position:'absolute',width:'100%',height:'100%',objectFit:'cover',filter:'blur(30px) brightness(.5)'}}/>}
 <Img src={address(photo.src)} style={{position:'absolute',width:'100%',height:'100%',objectFit:photo.fit??'cover'}}/>
</AbsoluteFill>;
const Frame:React.FC<{photos:Photo[];frame:number}>=({photos,frame})=>{
 const i=sceneAt(frame,photos.length);const photo=photos[i];
 // Effects after the seventh supplied module repeat scene 5's preset, not assets.
 const sourceFrame=frame<450?frame:254+((frame-450)%65);
 const active=layers.filter(l=>l.name!=='scene_'+(i+1)&&!l.name.startsWith('scene_')&&sourceFrame>=l.start&&sourceFrame<l.end).sort((a,b)=>a.track-b.track);
 const wrap=active.find(l=>l.effects.Offset&&l.end<=durationFor(photos.length));const wf=wrap?sourceFrame-wrap.start:0;
 const center=wrap?sample(wrap.effects.Offset['Shift Center To'],wf,[.5,.5]) as number[]:[.5,.5];
 const offset=(center[0]-.5)*1080;
 const blur=wrap?Number(sample(wrap.effects['Directional Blur']?.['Blur Length'],wf,0)):0;
 const base=(zoom=1,tx=0,ty=0)=><PhotoImage photo={photo} scale={zoom} x={tx} y={ty}/>;
 let content:React.ReactNode=<AbsoluteFill>{base()}</AbsoluteFill>;
 // Premiere adjustment layers modify the composite inside their transformed bounds.
 for(const l of active){
  const motion=l.effects.Motion;const transform=l.effects.Transform;
  if(!motion)continue;
  const t=sourceFrame-l.start;
  const pos=sample(motion.Position,t,[.5,.5]) as number[];
  const w=Number(sample(motion['Scale Width'],t,100))*10.8;
  const h=Number(sample(motion.Scale,t,100))*19.2;
  const x=pos[0]*1080-w/2,y=pos[1]*1920-h/2;
  if(transform){
   const zoom=Number(sample(transform['Scale Height'],t,100))/100;
   const tp=sample(transform.Position,t,[.5,.5]) as number[];
   content=<AbsoluteFill>{content}<div style={{position:'absolute',left:x,top:y,width:w,height:h,overflow:'hidden'}}><div style={{position:'absolute',left:-x,top:-y,width:1080,height:1920}}>{base(zoom,(tp[0]-.5)*1080,(tp[1]-.5)*1920)}</div></div></AbsoluteFill>;
  }else if(l.name==='Color Matte'){
   // Original synthetic-media color/blend encoding is not portable; match the
   // visible dark pulse rather than treating its serialized enum as a CSS enum.
   content=<AbsoluteFill>{content}<div style={{position:'absolute',left:x,top:y,width:w,height:h,background:'#08090b',opacity:.34,mixBlendMode:'multiply'}}/></AbsoluteFill>;
  }
 }
 if(!wrap)return <AbsoluteFill style={{overflow:'hidden'}}>{content}</AbsoluteFill>;
 const samples=blur>1?9:1;
 return <AbsoluteFill style={{overflow:'hidden',background:'#08090b'}}>{Array.from({length:samples},(_,s)=><AbsoluteFill key={s} style={{opacity:1/(s+1)}}>{[-1,0,1,2].map(tile=><AbsoluteFill key={tile} style={{translate:`${offset+tile*1080+(samples===1?0:(s/(samples-1)-.5)*blur)}px 0px`}}>{content}</AbsoluteFill>)}</AbsoluteFill>)}</AbsoluteFill>;
};
export const TravelStories:React.FC<Props>=({photos})=>{durationFor(photos.length);const frame=useCurrentFrame();return <Frame frame={frame} photos={photos}/>;};
