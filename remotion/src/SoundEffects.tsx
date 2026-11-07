import {Audio} from '@remotion/media';
import {interpolate, Sequence, staticFile, useVideoConfig} from 'remotion';

export type SoundEffectCue = {
  id: string;
  type: 'whoosh' | 'impact' | 'click' | 'dragon-whoosh' | 'dragon-camera';
  publicFile: string;
  timelineStartMs: number;
  durationMs?: number;
  volume?: number;
  speechDucking?: number;
};

const durationMs = {"dragon-whoosh": 700, "dragon-camera": 360, whoosh: 550, impact: 650, click: 90} as const;
const defaultVolume = {"dragon-whoosh": .14, "dragon-camera": .12, whoosh: 0.14, impact: 0.22, click: 0.09} as const;
const maximumVolume = {"dragon-whoosh": .18, "dragon-camera": .18, whoosh: 0.18, impact: 0.24, click: 0.12} as const;

export const SoundEffects: React.FC<{cues: SoundEffectCue[]}> = ({cues}) => {
  const {fps} = useVideoConfig();
  return (
    <>
      {cues.map((cue) => {
        const cueFrames = Math.max(1, Math.ceil(((cue.durationMs ?? durationMs[cue.type]) / 1000) * fps));
        const safeVolume = Math.min(cue.volume ?? defaultVolume[cue.type], maximumVolume[cue.type]);
        const speechDucking = Math.max(0.4, Math.min(cue.speechDucking ?? 0.72, 1));
        const attackEnd = (cue.type === 'impact' || cue.type.startsWith('dragon-')) ? 1 : Math.max(1, Math.round(cueFrames * 0.2));
        return (
          <Sequence
            key={cue.id}
            from={Math.round((cue.timelineStartMs / 1000) * fps)}
            durationInFrames={cueFrames}
            premountFor={fps}
          >
            <Audio
              src={staticFile(cue.publicFile)}
              volume={(relativeFrame) =>
                safeVolume *
                speechDucking *
                interpolate(relativeFrame, [0, Math.min(attackEnd, cueFrames / 2), cueFrames], [0, 1, 0], {
                  extrapolateLeft: 'clamp',
                  extrapolateRight: 'clamp',
                })
              }
            />
          </Sequence>
        );
      })}
    </>
  );
};
