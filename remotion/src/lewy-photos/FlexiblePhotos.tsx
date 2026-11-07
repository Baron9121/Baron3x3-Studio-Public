import React from 'react';
import {AbsoluteFill, Composition, Img, registerRoot, staticFile, useCurrentFrame} from 'remotion';
import {Scene, Photo} from './LewyPhotos';
import {Shot, Kind} from './timeline';
import manifest from './flexible-photos.json';
export type FlexibleProps={photos:Photo[]};
export const durationFor=(count:number)=>{if(!Number.isInteger(count)||count<1)throw new Error('At least one photo is required');return 25+Math.max(0,count-1)*30+20;};
export const FlexiblePhotos:React.FC<FlexibleProps>=({photos})=>{
 const f=useCurrentFrame();durationFor(photos.length);
 if(f<25||photos.length===1){const p=photos[f<25?0:photos.length-1];return <AbsoluteFill style={{background:'black'}}><Img src={staticFile(p.src)} style={{position:'absolute',left:180,top:320,width:720,height:1280,objectFit:'cover'}}/></AbsoluteFill>;}
 const i=Math.min(photos.length-2,Math.floor((f-25)/30));const local=Math.min(29,f-25-i*30);
 const kinds:Kind[]=['cutout','left','top','right'];
 const kind=kinds[i%4]==='cutout'&&!photos[i+1].cutout?'left':kinds[i%4];
 const shot:Shot={sourceStart:0,duration:30,kind,back:i+1,front:i+2,steps:kind==='cutout'?[3,7,11,15]:[3,7,11]};
 return <AbsoluteFill style={{background:'black'}}><div style={{position:'absolute',left:180,top:320,width:720,height:1280,overflow:'hidden'}}><Scene shot={shot} frame={local} photos={photos}/></div></AbsoluteFill>;
};
registerRoot(()=> <Composition id="BaronFlexiblePhotos" component={FlexiblePhotos} width={1080} height={1920} fps={25} durationInFrames={durationFor(manifest.photos.length)} defaultProps={manifest} calculateMetadata={({props})=>({durationInFrames:durationFor(props.photos.length)})}/>);
