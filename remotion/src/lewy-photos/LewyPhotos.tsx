import React, {useId} from 'react';
import {AbsoluteFill, Img, interpolate, staticFile, useCurrentFrame, useVideoConfig} from 'remotion';
import {locate, phaseAt, Shot} from './timeline';
export type Photo = {src:string; cutout?:string};
export type LewyPhotosProps = {photos:Photo[]; sourceTimeline?:boolean; fullBleed?:boolean};
const asset=(src:string)=>/^(https?:|data:|blob:)/.test(src)?src:staticFile(src);
// Seeded, stationary paper fibres: repeatable across renders and replacement photos.
const zig=(axis:'x'|'y',base:number,seed:number)=>Array.from({length:129},(_,i)=>{
 const t=i/128;const jitter=Math.sin(i*17.13+seed)*3.1+Math.sin(i*4.47+seed)*2.0;
 return axis==='x'?[base+jitter+11*Math.sin(t*15+seed),t*1280]:[t*720,base+jitter+35*Math.sin(t*4+seed)];
});
const path=(pts:number[][])=>pts.map((p,i)=>`${i?'L':'M'}${p[0].toFixed(2)},${p[1].toFixed(2)}`).join(' ');
const Tear:React.FC<{axis:'x'|'y';at:number;seed:number;thick?:number}>=({axis,at,seed,thick=8})=><svg width={720} height={1280} style={{position:'absolute',inset:0,pointerEvents:'none'}}><path d={path(zig(axis,at,seed))} stroke="#eeeae2" strokeWidth={thick} fill="none"/></svg>;
const Paper:React.FC<{tape?:boolean}>=({tape=false})=><>
 <svg width={720} height={1280} style={{position:'absolute',inset:0,pointerEvents:'none'}}>
 {Array.from({length:1500},(_,i)=><circle key={i} cx={(i*173.319)%720} cy={(i*97.723)%1280} r={i%5===0?1.1:.45} fill={i%3?'#fff':'#29261f'} opacity={.12}/>)}</svg>
 <Tear axis="x" at={240} seed={1} thick={2.5}/><Tear axis="x" at={490} seed={5} thick={2.2}/>
 <Tear axis="y" at={120} seed={2} thick={2.3}/><Tear axis="y" at={645} seed={3} thick={2.5}/>
 {tape&&<svg width={720} height={1280} style={{position:'absolute',inset:0}}><path d="M28 37 L664 46 L658 145 L78 141 L42 102 Z" fill="#e5e4df" opacity=".58"/></svg>}
</>;
const PhotoLayer:React.FC<{photo:Photo;cutout?:boolean;outline?:boolean;gray?:boolean}>=({photo,cutout=false,outline=false,gray=false})=>{
 const id='outline'+useId().replace(/:/g,'');
 return <>{outline&&<svg width="0" height="0" style={{position:'absolute'}}><defs><filter id={id} x="-10%" y="-10%" width="120%" height="120%"><feMorphology in="SourceAlpha" operator="dilate" radius="6" result="d"/><feFlood floodColor="#efeee8"/><feComposite in2="d" operator="in"/><feMerge><feMergeNode/><feMergeNode in="SourceGraphic"/></feMerge></filter></defs></svg>}
 <Img src={asset(cutout?photo.cutout!:photo.src)} style={{position:'absolute',inset:0,width:720,height:1280,objectFit:'cover',filter:[outline?`url(#${id})`:'',gray?'grayscale(1)':''].join(' ')}}/>
 </>;
};
const DecoratedPhoto:React.FC<{photo:Photo;slot:number}>=({photo,slot})=><>
 <PhotoLayer photo={photo}/>
 {slot===8&&<><div style={{position:'absolute',inset:0,clipPath:'polygon(0 17%,100% 37%,100% 82%,0 62%)'}}><PhotoLayer photo={photo} gray/></div><svg width={720} height={1280} style={{position:'absolute',inset:0}}><path d="M-10 218 L730 474 M-10 792 L730 1050" stroke="#eeece5" strokeWidth={12}/></svg></>}
 {slot===6&&<><Tear axis="y" at={345} seed={8} thick={10}/><svg width={720} height={1280} style={{position:'absolute',inset:0}}><path d="M-10 590 L730 865" stroke="#eeece5" strokeWidth={7}/></svg></>}
 {[4,9,10].includes(slot)&&<Tear axis="x" at={slot===10?490:320} seed={7} thick={12}/>}
 <Paper tape={slot===7}/>
 {slot===9&&<div style={{position:'absolute',left:42,top:975,width:650,height:60,background:'#edeae4',opacity:.65,rotate:'-3deg'}}/>}
</>;
const Flash:React.FC<{frame:number}>=({frame})=><AbsoluteFill style={{background:'white',opacity:interpolate(frame,[0,1,2,3],[.58,.29,.08,0],{extrapolateLeft:'clamp',extrapolateRight:'clamp'}),pointerEvents:'none'}}/>;
export const Scene:React.FC<{shot:Shot;frame:number;photos:Photo[]}>=({shot,frame,photos})=>{
 const p=phaseAt(frame,shot.steps);const back=photos[shot.back-1];const front=photos[shot.front-1];
 if(shot.kind==='cutout') {
  if(!front.cutout)throw new Error(`Photo ${shot.front} needs an automatically prepared cutout. Run tools/prepare.py.`);
  const amount=[0,1/3,2/3,1,1][p];
  return <AbsoluteFill style={{overflow:'hidden'}}>
   <AbsoluteFill style={{scale:interpolate(frame,[0,23],[1.034,1],{extrapolateRight:'clamp'})}}>
    <PhotoLayer photo={back}/>
    {p===4&&<><PhotoLayer photo={front}/><Paper tape/></>}
    <div style={{position:'absolute',inset:0,clipPath:`inset(0 ${(1-amount)*100}% 0 0)`}}>
     <div style={{position:'absolute',inset:0,rotate:`${p===1?2:p===2?(shot.tilt??0):0}deg`,transformOrigin:'50% 50%'}}><PhotoLayer photo={front} cutout outline/></div>
    </div>
    <Paper/>
   </AbsoluteFill>
   <Flash frame={frame}/>
  </AbsoluteFill>;
 }
 const dir=shot.kind==='right'?-1:1;
 const horizontal=shot.kind==='top';
 const scale=(!horizontal&&p===1)?1.25937:1;
 const x=horizontal?0:dir*([0,-542.84,-241.6,0][p]);
 const y=horizontal?[0,-810.7,-479.2,0][p]:0;
 const edge=horizontal?1280+y:dir===1?360+360*scale+x:360-360*scale+x;
 const boundary=zig(horizontal?'y':'x',edge,7);
 const clip=horizontal?`polygon(0px 0px,720px 0px,${[...boundary].reverse().map(q=>q.map(v=>v+'px').join(' ')).join(',')})`:dir===1?`polygon(0px 0px,${boundary.map(q=>q.map(v=>v+'px').join(' ')).join(',')},0px 1280px)`:`polygon(720px 0px,720px 1280px,${[...boundary].reverse().map(q=>q.map(v=>v+'px').join(' ')).join(',')})`;
 const settles=shot.settle&&frame===14;
 return <AbsoluteFill style={{overflow:'hidden'}}>
  <AbsoluteFill style={{scale:settles ? .95455 : 1}}>
   <div style={{position:'absolute',inset:0,translate:horizontal?`0px ${[0,309.4,641.1,1120.4][p]}px`:`${dir*[0,122.7,362.7,602.7][p]}px 0px`}}><DecoratedPhoto photo={back} slot={shot.back}/></div>
   {p>0&&<><div style={{position:'absolute',inset:0,clipPath:p===3?undefined:clip}}><div style={{position:'absolute',inset:0,translate:`${x}px ${y}px`,scale}}><DecoratedPhoto photo={front} slot={shot.front}/></div></div>{p<3&&<Tear axis={horizontal?'y':'x'} at={edge} seed={7} thick={12}/>}</>}
  </AbsoluteFill>
  <Flash frame={frame}/>
 </AbsoluteFill>;
};
/** Fixed reference timing; replacement photos are the only content inputs. No audio or captions. */
export const LewyPhotos:React.FC<LewyPhotosProps>=({photos,sourceTimeline=false,fullBleed=false})=>{
 const f=useCurrentFrame();const {width,height,fps}=useVideoConfig();
 if(fps!==25)throw new Error('LewyPhotos requires 25 FPS. Nest in a 25 FPS composition for reference timing.');
 if(photos.length!==10||photos.some(p=>!p.src))throw new Error('Provide exactly ten photos, slots 01–10.');
 const found=locate(f,sourceTimeline);
 const outer=fullBleed?Math.min(width/720,height/1280):Math.min(width/1080,height/1920);
 return <AbsoluteFill style={{backgroundColor:sourceTimeline?'transparent':'black'}}>{found&&<div style={{position:'absolute',width:720,height:1280,left:(width-720)/2,top:(height-1280)/2,scale:outer,overflow:'hidden'}}><Scene shot={found.shot} frame={found.local} photos={photos}/></div>}</AbsoluteFill>;
};
