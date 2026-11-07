import {AbsoluteFill, interpolate, useCurrentFrame} from 'remotion';
import {EffectCue, EffectLayer} from './EffectLayer';
import {SoundEffects} from './SoundEffects';

const cues: EffectCue[] = [
  {id: 'flash', type: 'flash', timelineStartMs: 900, timelineEndMs: 1200},
  {
    direction: 'right',
    id: 'whip',
    intensity: 1,
    timelineStartMs: 1900,
    timelineEndMs: 2450,
    type: 'whip',
  },
  {id: 'light-leak', type: 'light-leak', timelineStartMs: 3050, timelineEndMs: 3750},
  {id: 'paper-reveal', type: 'paper-reveal', timelineStartMs: 3750, timelineEndMs: 4650},
  {id: 'frame', type: 'film-frame', timelineStartMs: 4200, timelineEndMs: 5900},
  {id: 'rec', type: 'rec', timelineStartMs: 4200, timelineEndMs: 5900},
  {
    accentColor: '#ff174f',
    id: 'stat',
    label: 'LOKALNE EFEKTY GOTOWE',
    timelineStartMs: 6100,
    timelineEndMs: 8000,
    type: 'stat-card',
    value: '6',
  },
];

export const EffectsShowcase = () => {
  const frame = useCurrentFrame();
  const x = interpolate(frame, [0, 240], [-130, 130]);
  return (
    <AbsoluteFill style={{backgroundColor: '#10131a', overflow: 'hidden'}}>
      <AbsoluteFill
        style={{
          background:
            'radial-gradient(circle at 25% 25%, #273a68 0%, transparent 46%), radial-gradient(circle at 78% 72%, #6a1537 0%, transparent 42%)',
          scale: 1.15,
          translate: `${x}px 0px`,
        }}
      />
      <AbsoluteFill
        style={{
          alignItems: 'center',
          color: '#ffffff',
          display: 'flex',
          fontFamily: 'Arial, sans-serif',
          fontSize: 96,
          fontWeight: 950,
          justifyContent: 'center',
          textAlign: 'center',
          textShadow: '0 10px 35px rgba(0,0,0,.65)',
        }}
      >
        BARON3X3
        <div style={{color: '#ffcc00', fontSize: 42, marginTop: 28}}>
          BIBLIOTEKA EFEKTÓW
        </div>
      </AbsoluteFill>
      <EffectLayer cues={cues} />
      <SoundEffects
        cues={[
          {
            id: 'sfx-whoosh',
            publicFile: 'sfx/whoosh-soft.wav',
            timelineStartMs: 1900,
            type: 'whoosh',
            volume: 0.3,
          },
          {
            id: 'sfx-click',
            publicFile: 'sfx/click.wav',
            timelineStartMs: 4200,
            type: 'click',
            volume: 0.22,
          },
          {
            id: 'sfx-impact',
            publicFile: 'sfx/impact-low.wav',
            timelineStartMs: 6100,
            type: 'impact',
            volume: 0.34,
          },
        ]}
      />
    </AbsoluteFill>
  );
};
