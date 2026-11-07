export type Kind = 'cutout' | 'left' | 'right' | 'top';
export type Shot = {sourceStart: number; duration: number; kind: Kind; back: number; front: number; steps: readonly number[]; settle?: boolean; tilt?: number};
// Source frame indices are zero based. End frames are exclusive.
export const shots: readonly Shot[] = [
 {sourceStart:0,duration:24,kind:'cutout',back:1,front:2,steps:[4,7,11,15],tilt:0},
 {sourceStart:24,duration:15,kind:'left',back:3,front:4,steps:[3,7,11],settle:true},
 {sourceStart:39,duration:15,kind:'top',back:5,front:6,steps:[3,7,11],settle:true},
 {sourceStart:286,duration:24,kind:'cutout',back:1,front:7,steps:[4,8,12,16],tilt:-2},
 {sourceStart:310,duration:15,kind:'left',back:8,front:9,steps:[3,7,11],settle:true},
 {sourceStart:325,duration:15,kind:'top',back:7,front:6,steps:[3,7,11],settle:true},
 {sourceStart:340,duration:12,kind:'right',back:7,front:10,steps:[3,7,11]},
 {sourceStart:352,duration:23,kind:'cutout',back:1,front:2,steps:[3,7,11,15],tilt:0},
 {sourceStart:375,duration:15,kind:'left',back:3,front:4,steps:[4,8,12]},
];
export const montageDuration = shots.reduce((sum,s)=>sum+s.duration,0);
export const phaseAt = (frame:number,steps:readonly number[]) => steps.filter(n=>frame>=n).length;
export const locate = (frame:number,sourceTimeline=false) => {
 let cursor=0;
 for (let i=0;i<shots.length;i++) {const shot=shots[i];const start=sourceTimeline?shot.sourceStart:cursor;if(frame>=start&&frame<start+shot.duration)return {shot,index:i,local:frame-start};cursor+=shot.duration;}
 return null;
};
