import React from 'react';
import {Composition,registerRoot} from 'remotion';
import {LewyPhotos} from './LewyPhotos';
import {montageDuration} from './timeline';
const photos=Array.from({length:10},(_,i)=>({src:`lewy-photos/${String(i+1).padStart(2,'0')}.png`,...([1,6].includes(i)?{cutout:`lewy-photos/${String(i+1).padStart(2,'0')}-cutout.png`}:{})}));
const Root=()=> <>
 <Composition id="LewyPhotoMontage" component={LewyPhotos} width={1080} height={1920} fps={25} durationInFrames={montageDuration} defaultProps={{photos}}/>
 <Composition id="LewyPhotoOverlay" component={LewyPhotos} width={1080} height={1920} fps={25} durationInFrames={452} defaultProps={{photos,sourceTimeline:true}}/>
</>;
registerRoot(Root);
