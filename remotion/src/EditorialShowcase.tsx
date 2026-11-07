import {AbsoluteFill, Sequence, useVideoConfig} from 'remotion';
import {OverlayMedia} from './BaronReel';

const seconds = (value: number, fps: number) => Math.round(value * fps);

export const EditorialShowcase = () => {
  const {fps} = useVideoConfig();

  return (
    <AbsoluteFill style={{backgroundColor: '#000'}}>
      <Sequence durationInFrames={seconds(4, fps)}>
        <OverlayMedia
          overlay={{
            accentColor: '#ff174f',
            headline: 'AKCJA I REAKCJA',
            id: 'editorial-split',
            kicker: 'MOCNY BEAT',
            kind: 'video',
            motion: 'still',
            objectPosition: '50% 50%',
            presentation: 'split',
            publicFile: 'assets/showcase-action.mp4',
            secondaryKind: 'video',
            secondaryObjectPosition: '50% 50%',
            secondaryPublicFile: 'assets/showcase-action.mp4',
            secondarySourceStartMs: 5700,
            sourceStartMs: 2500,
            timelineEndMs: 4000,
            timelineStartMs: 0,
          }}
        />
      </Sequence>
      <Sequence from={seconds(4, fps)} durationInFrames={seconds(4, fps)}>
        <OverlayMedia
          overlay={{
            accentColor: '#ff174f',
            headline: 'WARSZAWA',
            id: 'editorial-stack',
            kicker: 'MIEJSCE HISTORII',
            kind: 'image',
            motion: 'push-in',
            objectPosition: '50% 50%',
            presentation: 'stack',
            publicFile: 'assets/showcase-warsaw.jpg',
            secondaryKind: 'image',
            secondaryObjectPosition: '50% 50%',
            secondaryPublicFile: 'assets/showcase-warsaw-2.jpg',
            secondarySourceStartMs: 0,
            sourceStartMs: 0,
            timelineEndMs: 8000,
            timelineStartMs: 4000,
          }}
        />
      </Sequence>
    </AbsoluteFill>
  );
};
