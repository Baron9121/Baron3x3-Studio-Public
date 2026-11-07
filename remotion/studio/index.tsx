import {Composition, registerRoot} from 'remotion';
import {StudioReel, type Props} from './StudioReel';
const defaults:Props={plan:{version:1,project:'demo',fps:30,width:1080,height:1920,aroll:{source:'aroll.mp4',duration:3,sha256:''},elements:[]},theme:{green:'#39E508',white:'#FFFFFF',black:'#0B0B0B',fontFamily:'Arial Black, Arial, sans-serif'}};
const Root=()=> <Composition id="BaronStudio" component={StudioReel} defaultProps={defaults} width={1080} height={1920} fps={30} durationInFrames={90} calculateMetadata={({props})=>({durationInFrames:Math.ceil(props.plan.aroll.duration*props.plan.fps),width:props.plan.width,height:props.plan.height,fps:props.plan.fps})}/>;
registerRoot(Root);
