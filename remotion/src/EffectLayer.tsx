import {lightLeak} from '@remotion/effects/light-leak';
import {
  AbsoluteFill,
  Easing,
  interpolate,
  Solid,
  useCurrentFrame,
  useVideoConfig,
} from 'remotion';

export type EffectCueType =
  | 'flash'
  | 'whip'
  | 'light-leak'
  | 'film-frame'
  | 'rec'
  | 'stat-card'
  | 'kinetic-text'
  | 'audio-waveform'
  | 'paper-reveal';

export type EffectCue = {
  id: string;
  type: EffectCueType;
  timelineStartMs: number;
  timelineEndMs: number;
  intensity?: number;
  direction?: 'left' | 'right';
  value?: string;
  label?: string;
  accentColor?: string;
  placement?: 'top' | 'top-left' | 'top-right' | 'center';
};

const clamp = {
  extrapolateLeft: 'clamp' as const,
  extrapolateRight: 'clamp' as const,
};

type StatMetric = {
  target: number;
  unit: string;
  display?: string;
};

const FRACTION_RE = /^\s*(\d+(?:[.,]\d+)?)\s*\/\s*(\d+(?:[.,]\d+)?)\s*$/;

const parseStatMetrics = (value: string): StatMetric[] => {
  // "17 / 21", "5 / 10", "35 / 5" are a single fraction, rendered as a static
  // pair (numerator / denominator) rather than two discrete counted numbers.
  const fraction = value.match(FRACTION_RE);
  if (fraction) {
    return [{
      target: Number(fraction[2].replace(',', '.')),
      unit: '',
      display: `${fraction[1]} / ${fraction[2]}`,
    }];
  }
  const matches = Array.from(
    value.matchAll(/(\d+(?:[.,]\d+)?)\s*([\p{L}%]+)?/gu),
  );
  if (matches.length === 0) {
    return [{target: 0, unit: value.trim()}];
  }
  return matches.map((match) => ({
    target: Number(match[1].replace(',', '.')),
    unit: (match[2] ?? '').toUpperCase(),
  }));
};

const Cue: React.FC<{cue: EffectCue}> = ({cue}) => {
  const frame = useCurrentFrame();
  const {fps, height, width} = useVideoConfig();
  const duration = Math.max(
    1,
    Math.round(((cue.timelineEndMs - cue.timelineStartMs) / 1000) * fps),
  );
  const localFrame = frame - Math.round((cue.timelineStartMs / 1000) * fps);
  const intensity = cue.intensity ?? 1;
  const pulse = interpolate(
    localFrame,
    [0, Math.max(1, duration * 0.42), duration],
    [0, 1, 0],
    clamp,
  );
  const reveal = interpolate(localFrame, [0, Math.max(1, duration * 0.22)], [0, 1], {
    ...clamp,
    easing: Easing.bezier(0.16, 1, 0.3, 1),
  });

  if (cue.type === 'flash') {
    return (
      <AbsoluteFill
        style={{
          backgroundColor: '#ffffff',
          mixBlendMode: 'screen',
          opacity: pulse * 0.72 * intensity,
        }}
      />
    );
  }

  if (cue.type === 'whip') {
    const sign = cue.direction === 'left' ? -1 : 1;
    return (
      <AbsoluteFill style={{overflow: 'hidden', pointerEvents: 'none'}}>
        {[-2, -1, 0, 1, 2].map((offset) => (
          <div
            key={offset}
            style={{
              background:
                offset % 2 === 0
                  ? 'linear-gradient(90deg, transparent, rgba(255,255,255,.5), transparent)'
                  : 'linear-gradient(90deg, transparent, rgba(255,35,90,.36), transparent)',
              filter: `blur(${12 + Math.abs(offset) * 8}px)`,
              height: '130%',
              left: '-40%',
              opacity: pulse * (0.34 - Math.abs(offset) * 0.035) * intensity,
              position: 'absolute',
              rotate: `${offset * 3}deg`,
              top: '-15%',
              translate: `${sign * (pulse * 420 + offset * 85)}px 0px`,
              width: '180%',
            }}
          />
        ))}
      </AbsoluteFill>
    );
  }

  if (cue.type === 'light-leak') {
    return (
      <AbsoluteFill
        style={{
          mixBlendMode: 'screen',
          opacity: 0.42 * intensity,
          pointerEvents: 'none',
        }}
      >
        <Solid
          width={width}
          height={height}
          effects={[
            lightLeak({
              hueShift: 0,
              progress: interpolate(localFrame, [0, Math.max(1, duration - 1)], [0, 1], clamp),
              seed: 33,
            }),
          ]}
        />
      </AbsoluteFill>
    );
  }

  if (cue.type === 'paper-reveal') {
    const tearProgress = interpolate(
      localFrame,
      [0, Math.max(1, duration * 0.78)],
      [0, 1],
      {
        ...clamp,
        easing: Easing.bezier(0.76, 0, 0.24, 1),
      },
    );
    const paperTexture =
      'repeating-linear-gradient(8deg, rgba(90,65,42,.055) 0px, rgba(90,65,42,.055) 1px, transparent 1px, transparent 8px), radial-gradient(circle at 24% 18%, #fffef8 0%, #f1eadc 72%, #d8cbb7 100%)';
    return (
      <AbsoluteFill style={{overflow: 'hidden', pointerEvents: 'none'}}>
        <div
          style={{
            background: paperTexture,
            boxShadow: '0 18px 42px rgba(0,0,0,.48)',
            clipPath:
              'polygon(0 0,100% 0,100% 93%,97% 96%,93% 92%,89% 97%,85% 94%,80% 98%,76% 93%,71% 96%,66% 92%,61% 97%,57% 94%,52% 96%,48% 92%,43% 95%,38% 93%,34% 98%,29% 94%,24% 97%,19% 92%,14% 96%,10% 93%,6% 98%,2% 94%,0 96%)',
            height: '58%',
            left: 0,
            position: 'absolute',
            top: 0,
            translate: `0 ${-tearProgress * 112}%`,
            width: '100%',
          }}
        />
        <div
          style={{
            background: paperTexture,
            boxShadow: '0 -18px 42px rgba(0,0,0,.48)',
            clipPath:
              'polygon(0 7%,3% 4%,8% 8%,12% 3%,17% 7%,21% 4%,26% 9%,31% 5%,35% 8%,40% 3%,45% 7%,50% 4%,55% 9%,59% 5%,64% 8%,69% 3%,74% 7%,78% 5%,83% 9%,88% 4%,92% 8%,96% 3%,100% 7%,100% 100%,0 100%)',
            bottom: 0,
            height: '58%',
            left: 0,
            position: 'absolute',
            translate: `0 ${tearProgress * 112}%`,
            width: '100%',
          }}
        />
        <div
          style={{
            background:
              'linear-gradient(90deg, transparent, rgba(255,255,255,.95) 20%, rgba(214,197,174,.85) 52%, rgba(255,255,255,.9) 78%, transparent)',
            filter: 'blur(1.5px)',
            height: 16,
            left: '-8%',
            opacity: interpolate(tearProgress, [0, 0.76, 1], [0.95, 0.42, 0], clamp),
            position: 'absolute',
            rotate: '-1.2deg',
            top: '49.6%',
            width: '116%',
          }}
        />
      </AbsoluteFill>
    );
  }

  if (cue.type === 'film-frame') {
    return (
      <AbsoluteFill
        style={{
          boxShadow: `inset 0 0 ${85 * intensity}px ${28 * intensity}px rgba(0,0,0,.9)`,
          opacity: reveal,
        }}
      >
        <div
          style={{
            border: '3px solid rgba(255,255,255,.72)',
            bottom: 58,
            left: 46,
            position: 'absolute',
            right: 46,
            top: 58,
          }}
        />
      </AbsoluteFill>
    );
  }

  if (cue.type === 'rec') {
    const blink = Math.floor(localFrame / Math.max(1, Math.round(fps * 0.45))) % 2;
    return (
      <AbsoluteFill style={{opacity: reveal}}>
        <div
          style={{
            alignItems: 'center',
            color: '#ffffff',
            display: 'flex',
            fontFamily: 'Arial, sans-serif',
            fontSize: 32,
            fontWeight: 800,
            gap: 14,
            left: 52,
            letterSpacing: 3,
            position: 'absolute',
            top: 58,
          }}
        >
          <span
            style={{
              backgroundColor: '#ff174f',
              borderRadius: '50%',
              height: 18,
              opacity: blink ? 1 : 0.35,
              width: 18,
            }}
          />
          REC
        </div>
      </AbsoluteFill>
    );
  }

  if (cue.type === 'kinetic-text') {
    const words = (cue.value ?? '').trim().split(/\s+/).filter(Boolean);
    const leadWords = words.slice(0, -1);
    const keyword = words.at(-1) ?? '';
    const accent = cue.accentColor ?? '#ff174f';
    const sidePlacement = cue.placement === 'top-left' || cue.placement === 'top-right';
    const exit = interpolate(
      localFrame,
      [Math.max(1, duration - fps * 0.24), duration],
      [1, 0],
      clamp,
    );
    return (
      <AbsoluteFill
        style={{
          opacity: exit,
          overflow: 'hidden',
          pointerEvents: 'none',
        }}
      >
        <div
          style={{
            background:
              'linear-gradient(180deg, rgba(0,0,0,.78) 0%, rgba(0,0,0,.43) 58%, transparent 100%)',
            height: 500,
            left: 0,
            opacity: interpolate(localFrame, [0, fps * 0.18], [0, 1], clamp),
            position: 'absolute',
            top: 0,
            width: '100%',
          }}
        />
        <div
          style={{
            boxSizing: 'border-box',
            fontFamily: 'Arial, sans-serif',
            left: cue.placement === 'top-right' ? '50%' : 0,
            padding: sidePlacement ? '0 42px' : '0 72px',
            position: 'absolute',
            textAlign: 'center',
            top: cue.placement === 'center' ? height * 0.31 : sidePlacement ? 132 : 92,
            translate: `0 ${interpolate(localFrame, [0, fps * 0.3], [32, 0], {
              ...clamp,
              easing: Easing.bezier(0.16, 1, 0.3, 1),
            })}px`,
            width: sidePlacement ? '50%' : '100%',
          }}
        >
          <div
            style={{
              alignItems: 'center',
              display: 'flex',
              gap: 20,
              justifyContent: 'center',
              opacity: reveal,
            }}
          >
            <div
              style={{
                background: `linear-gradient(90deg, transparent, ${accent})`,
                height: 3,
                scale: `${reveal} 1`,
                transformOrigin: 'right center',
                width: sidePlacement ? 36 : 76,
              }}
            />
            <div
              style={{
                color: accent,
                fontSize: sidePlacement ? 30 : 42,
                fontWeight: 900,
                letterSpacing: sidePlacement ? 6 : 10,
                lineHeight: 1,
                textShadow: `0 0 28px ${accent}55`,
              }}
            >
              {cue.label}
            </div>
            <div
              style={{
                background: `linear-gradient(90deg, ${accent}, transparent)`,
                height: 3,
                scale: `${reveal} 1`,
                transformOrigin: 'left center',
                width: sidePlacement ? 36 : 76,
              }}
            />
          </div>
          <div
            style={{
              alignItems: 'baseline',
              display: 'flex',
              flexWrap: 'wrap',
              gap: '0 22px',
              justifyContent: 'center',
              marginTop: 24,
            }}
          >
            {leadWords.map((word, index) => {
              const wordStart = fps * (0.08 + index * 0.075);
              const wordEnd = wordStart + fps * 0.24;
              return (
                <div
                  key={`${word}-${index}`}
                  style={{
                    clipPath: `inset(${interpolate(
                      localFrame,
                      [wordStart, wordEnd],
                      [100, 0],
                      clamp,
                    )}% 0 0 0)`,
                    color: '#ffffff',
                    fontSize: sidePlacement ? 48 : 70,
                    fontWeight: 950,
                    letterSpacing: -3.5,
                    lineHeight: 0.96,
                    opacity: interpolate(localFrame, [wordStart, wordEnd], [0, 1], clamp),
                    textShadow: '0 7px 28px rgba(0,0,0,.92)',
                    translate: `0 ${interpolate(
                      localFrame,
                      [wordStart, wordEnd],
                      [34, 0],
                      {
                        ...clamp,
                        easing: Easing.bezier(0.16, 1, 0.3, 1),
                      },
                    )}px`,
                  }}
                >
                  {word}
                </div>
              );
            })}
          </div>
          <div
            style={{
              color: 'transparent',
              fontSize: sidePlacement ? 80 : 116,
              fontWeight: 950,
              letterSpacing: -5,
              lineHeight: 0.92,
              marginTop: 10,
              opacity: interpolate(localFrame, [fps * 0.3, fps * 0.54], [0, 1], clamp),
              scale: interpolate(localFrame, [fps * 0.3, fps * 0.58], [0.82, 1], {
                ...clamp,
                easing: Easing.bezier(0.16, 1, 0.3, 1),
                output: 'perceptual-scale',
              }),
              textShadow: `0 8px 34px ${accent}44`,
              WebkitBackgroundClip: 'text',
              backgroundImage: `linear-gradient(180deg, #ffffff 0%, #ffd4de 42%, ${accent} 100%)`,
            }}
          >
            {keyword}
          </div>
          <div
            style={{
              background: `linear-gradient(90deg, transparent, ${accent}, transparent)`,
              height: 4,
              margin: '18px auto 0',
              opacity: interpolate(localFrame, [fps * 0.38, fps * 0.62], [0, 0.9], clamp),
              scale: `${interpolate(localFrame, [fps * 0.38, fps * 0.62], [0, 1], {
                ...clamp,
                easing: Easing.bezier(0.16, 1, 0.3, 1),
              })} 1`,
              width: sidePlacement ? 260 : 420,
            }}
          />
          </div>
      </AbsoluteFill>
    );
  }

  if (cue.type === 'audio-waveform') {
    const accent = cue.accentColor ?? '#ff174f';
    const sidePlacement = cue.placement === 'top-left' || cue.placement === 'top-right';
    return (
      <AbsoluteFill
        style={{
          alignItems: 'center',
          display: 'flex',
          justifyContent: 'center',
          opacity: interpolate(
            localFrame,
            [0, fps * 0.18, Math.max(fps * 0.2, duration - fps * 0.2), duration],
            [0, 1, 1, 0],
            clamp,
          ),
          pointerEvents: 'none',
        }}
      >
        <div
          style={{
            left: cue.placement === 'top-right' ? '52%' : cue.placement === 'top-left' ? '4%' : undefined,
            position: cue.placement === 'center' ? 'relative' : 'absolute',
            textAlign: 'center',
            top: cue.placement === 'center' ? undefined : 128,
            width: sidePlacement ? '44%' : '84%',
          }}
        >
          <div
            style={{
              color: '#fff',
              fontFamily: 'Arial, sans-serif',
              fontSize: sidePlacement ? 30 : 42,
              fontWeight: 900,
              letterSpacing: sidePlacement ? 3 : 6,
              marginBottom: 30,
              textShadow: '0 5px 24px rgba(0,0,0,.95)',
            }}
          >
            {cue.label ?? 'GŁOS Z BOISKA'}
          </div>
          <div style={{alignItems: 'center', display: 'flex', gap: sidePlacement ? 5 : 9, height: 118}}>
            {Array.from({length: 28}).map((_, index) => {
              const wave = (Math.sin(localFrame * 0.34 + index * 0.82) + 1) / 2;
              const envelope = 0.38 + Math.sin((index / 27) * Math.PI) * 0.62;
              return (
                <div
                  key={index}
                  style={{
                    background: `linear-gradient(180deg, #fff, ${accent})`,
                    borderRadius: 999,
                    boxShadow: `0 0 16px ${accent}55`,
                    flex: 1,
                    height: 12 + wave * envelope * 96,
                  }}
                />
              );
            })}
          </div>
        </div>
      </AbsoluteFill>
    );
  }

  const accent = cue.accentColor ?? '#ff174f';
  const metrics = parseStatMetrics(cue.value ?? '3×3');
  const cardOpacity = interpolate(
    localFrame,
    [0, Math.max(1, fps * 0.16), Math.max(2, duration - fps * 0.28), duration],
    [0, 1, 1, 0],
    clamp,
  );
  const entranceFlash = interpolate(
    localFrame,
    [0, Math.max(1, fps * 0.08), Math.max(2, fps * 0.28)],
    [0, 0.48, 0],
    clamp,
  );
  return (
    <AbsoluteFill
      style={{
        alignItems: 'center',
        background:
          'radial-gradient(circle at 50% 45%, #19040b 0%, #080103 35%, #020202 72%)',
        display: 'flex',
        justifyContent: 'center',
        opacity: cardOpacity,
        overflow: 'hidden',
      }}
    >
      <div
        style={{
          background:
            'linear-gradient(105deg, transparent 30%, rgba(255,23,79,.12) 48%, transparent 66%)',
          height: '140%',
          left: '-75%',
          opacity: interpolate(
            localFrame,
            [0, Math.max(1, fps * 1.25)],
            [0.2, 0.82],
            clamp,
          ),
          position: 'absolute',
          rotate: '-8deg',
          top: '-20%',
          translate: `${interpolate(
            localFrame,
            [0, Math.max(1, duration)],
            [0, width * 1.9],
            clamp,
          )}px 0px`,
          width: '55%',
        }}
      />
      <div
        style={{
          backgroundColor: '#ffffff',
          inset: 0,
          mixBlendMode: 'screen',
          opacity: entranceFlash,
          position: 'absolute',
        }}
      />
      <div
        style={{
          fontFamily: 'Arial, sans-serif',
          position: 'relative',
          textAlign: 'center',
          width: '88%',
        }}
      >
        <div
          style={{
            color: '#ffffff',
            fontSize: 38,
            fontWeight: 850,
            letterSpacing: 4,
            marginBottom: 62,
            opacity: interpolate(
              localFrame,
              [fps * 0.32, fps * 0.62],
              [0, 1],
              clamp,
            ),
            textTransform: 'uppercase',
          }}
        >
          {cue.label ?? 'MOCNY FAKT'}
        </div>
        <div
          style={{
            alignItems: 'stretch',
            display: 'flex',
            gap: 38,
            justifyContent: 'center',
          }}
        >
          {metrics.map((metric, index) => {
            const countStart = fps * (0.2 + index * 0.18);
            const countEnd = countStart + fps * 0.76;
            const metricProgress = interpolate(
              localFrame,
              [countStart, countEnd],
              [0, 1],
              {
                ...clamp,
                easing: Easing.bezier(0.16, 1, 0.3, 1),
              },
            );
            const hasStaticDisplay = typeof metric.display === 'string';
            // Static fractions (e.g. "5 / 10") are shown at full opacity and
            // scale from the moment the card appears, no per-number count-up.
            const entrance = hasStaticDisplay
              ? 1
              : interpolate(
                  localFrame,
                  [countStart - fps * 0.08, countStart + fps * 0.16],
                  [0, 1],
                  clamp,
                );
            const entranceScale = hasStaticDisplay
              ? 1
              : interpolate(
                  localFrame,
                  [countStart, countStart + fps * 0.22, countEnd],
                  [0.72, 1.06, 1],
                  {
                    ...clamp,
                    easing: Easing.bezier(0.16, 1, 0.3, 1),
                    output: 'perceptual-scale',
                  },
                );
            const displayed = hasStaticDisplay
              ? (metric.display as string)
              : Number.isInteger(metric.target)
              ? Math.round(metric.target * metricProgress)
              : (metric.target * metricProgress).toFixed(1);
            return (
              <div
                key={`${metric.target}-${metric.unit}-${index}`}
                style={{
                  flex: 1,
                  maxWidth: metrics.length > 1 ? 420 : 720,
                  opacity: entrance,
                  scale: entranceScale,
                }}
              >
                <div
                  style={{
                    background: `linear-gradient(125deg, #fff 0%, #ffc2d0 24%, ${accent} 66%, #b5002f 100%)`,
                    backgroundClip: 'text',
                    color: 'transparent',
                    fontSize: metrics.length > 1 ? 270 : 330,
                    fontWeight: 950,
                    letterSpacing: -18,
                    lineHeight: 0.82,
                    textShadow: `0 0 ${24 + metricProgress * 42}px ${accent}66`,
                  }}
                >
                  {displayed}
                </div>
                <div
                  style={{
                    color: '#ffffff',
                    fontSize: 58,
                    fontWeight: 900,
                    letterSpacing: 3,
                    marginTop: 28,
                    opacity: interpolate(
                      localFrame,
                      [countEnd - fps * 0.24, countEnd + fps * 0.04],
                      [0, 1],
                      clamp,
                    ),
                  }}
                >
                  {metric.unit}
                </div>
                <div
                  style={{
                    background: `linear-gradient(90deg, transparent, ${accent}, transparent)`,
                    height: 4,
                    margin: '24px auto 0',
                    opacity: 0.9,
                    scale: `${interpolate(
                      localFrame,
                      [countStart, countEnd],
                      [0, 1],
                      clamp,
                    )} 1`,
                    width: '78%',
                  }}
                />
              </div>
            );
          })}
        </div>
      </div>
    </AbsoluteFill>
  );
};

export const EffectLayer: React.FC<{cues: EffectCue[]}> = ({cues}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const nowMs = (frame / fps) * 1000;
  return (
    <>
      {cues
        .filter((cue) => nowMs >= cue.timelineStartMs && nowMs < cue.timelineEndMs)
        .map((cue) => (
          <Cue key={cue.id} cue={cue} />
        ))}
    </>
  );
};
