import {AbsoluteFill, Sequence, useVideoConfig} from 'remotion';
import {OverlayMedia} from './BaronReel';

const seconds = (value: number, fps: number) => Math.round(value * fps);

export const BrollShowcase = () => {
  const {fps} = useVideoConfig();

  return (
    <AbsoluteFill style={{backgroundColor: '#000'}}>
      <Sequence durationInFrames={seconds(4, fps)}>
        <OverlayMedia
          overlay={{
            id: 'showcase-full',
            kind: 'video',
            motion: 'push-in',
            objectPosition: '50% 50%',
            presentation: 'full',
            publicFile: 'assets/showcase-action.mp4',
            sourceStartMs: 2500,
            timelineEndMs: 4000,
            timelineStartMs: 0,
          }}
        />
      </Sequence>
      <Sequence from={seconds(4, fps)} durationInFrames={seconds(4, fps)}>
        <OverlayMedia
          overlay={{
            id: 'showcase-editorial',
            kind: 'image',
            motion: 'pan-right',
            objectPosition: '50% 50%',
            presentation: 'editorial',
            publicFile: 'assets/showcase-warsaw.jpg',
            sourceStartMs: 0,
            timelineEndMs: 8000,
            timelineStartMs: 4000,
          }}
        />
      </Sequence>
      <Sequence from={seconds(8, fps)} durationInFrames={seconds(4, fps)}>
        <OverlayMedia
          overlay={{
            id: 'showcase-archive',
            kind: 'video',
            motion: 'pull-out',
            objectPosition: '50% 50%',
            presentation: 'archive',
            publicFile: 'assets/showcase-action.mp4',
            sourceStartMs: 5200,
            timelineEndMs: 12000,
            timelineStartMs: 8000,
          }}
        />
      </Sequence>
    </AbsoluteFill>
  );
};
