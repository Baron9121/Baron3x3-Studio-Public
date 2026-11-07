import {InstagramStories,durationFor} from './matte-photos/InstagramStories';
import mattePhotos from './matte-photos/default.json';
import {Composition} from 'remotion';
import rawJob from '../public/job.json';
import {BaronReel} from './BaronReel';
import {BrollShowcase} from './BrollShowcase';
import {EffectsShowcase} from './EffectsShowcase';
import {EditorialShowcase} from './EditorialShowcase';
import {SmokeTest} from './SmokeTest';
import {GlobeSpin} from './GlobeSpin';

const job = rawJob as {timeline: {durationInFrames: number; fps: number; width: number; height: number}};

export const RemotionRoot = () => {
  return (
    <>
      <Composition id="BaronMattePhotos" component={InstagramStories} width={1080} height={1920} fps={30} durationInFrames={durationFor(mattePhotos.photos.length)} defaultProps={mattePhotos} calculateMetadata={({props})=>({durationInFrames:durationFor(props.photos.length)})}/>
      <Composition
        id="BaronReel"
        component={BaronReel}
        durationInFrames={Math.max(1, job.timeline.durationInFrames)}
        fps={job.timeline.fps}
        width={job.timeline.width}
        height={job.timeline.height}
      />
      <Composition
        id="BaronEffectsShowcase"
        component={EffectsShowcase}
        durationInFrames={240}
        fps={30}
        width={1080}
        height={1920}
      />
      <Composition
        id="BaronBrollShowcase"
        component={BrollShowcase}
        durationInFrames={360}
        fps={30}
        width={1080}
        height={1920}
      />
      <Composition
        id="BaronEditorialShowcase"
        component={EditorialShowcase}
        durationInFrames={240}
        fps={30}
        width={1080}
        height={1920}
      />
      <Composition
        id="RemotionSmokeTest"
        component={SmokeTest}
        durationInFrames={60}
        fps={30}
        width={1080}
        height={1920}
      />
      <Composition
        id="GlobeSpin"
        component={GlobeSpin}
        durationInFrames={180}
        fps={30}
        width={1080}
        height={1920}
      />
    </>
  );
};
