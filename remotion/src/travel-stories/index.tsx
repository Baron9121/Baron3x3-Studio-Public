import React from 'react';
import {Composition,registerRoot} from 'remotion';
import {TravelStories,durationFor,Props} from './TravelStories';
import manifest from './photos.json';
const props=manifest as Props;
registerRoot(()=> <Composition id="TravelStories" component={TravelStories} width={1080} height={1920} fps={30} durationInFrames={durationFor(props.photos.length)} defaultProps={props} calculateMetadata={({props})=>({durationInFrames:durationFor(props.photos.length)})}/>);
