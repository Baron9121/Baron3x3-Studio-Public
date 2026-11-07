import {Video} from '@remotion/media';
import {chromaticAberration} from '@remotion/effects/chromatic-aberration';
import {zoomBlur} from '@remotion/effects/zoom-blur';
import {
  AbsoluteFill,
  CanvasImage,
  Easing,
  interpolate,
  Sequence,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
} from 'remotion';
import rawJob from '../public/job.json';
import {EffectCue, EffectLayer} from './EffectLayer';
import {SoundEffectCue, SoundEffects} from './SoundEffects';
import {WordCaptions} from './WordCaptions';
import {sanitizeTimeline, Scene} from './timeline';

export type CaptionStyle = 'green-word' | 'white-outline';
export type ZoomLevel = 'wide' | 'medium' | 'close';
export type ZoomEffect = 'smooth' | 'blur' | 'rgb' | 'split';
export type OverlayPresentation =
  | 'full'
  | 'editorial'
  | 'archive'
  | 'split'
  | 'stack'
  | 'cutout'
  | 'paper-collage';
export type OverlayMotion =
  | 'push-in'
  | 'pull-out'
  | 'pan-left'
  | 'pan-right'
  | 'still';

export type Job = {
  source: {publicFile: string};
  captionStyle?: CaptionStyle;
  colorGrade?: {
    contrast: number;
    saturation: number;
    brightness: number;
    sepia: number;
  };
  visualBeats?: Array<{
    timelineStartMs: number;
    timelineEndMs: number;
    zoomLevel: ZoomLevel;
    transitionEffect: ZoomEffect;
    reason: string;
  }>;
  edits: Array<{
    id: string;
    sourceStartMs: number;
    timelineStartMs: number;
    timelineEndMs: number;
    scaleFrom?: number;
    scaleTo?: number;
    objectPosition?: string;
    translate?: string;
  }>;
  overlays?: Array<{
    id: string;
    assetId?: string | null;
    kind?: 'video' | 'image';
    publicFile: string;
    secondaryAssetId?: string | null;
    secondaryKind?: 'video' | 'image' | null;
    secondaryPublicFile?: string | null;
    secondarySourceStartMs?: number;
    secondaryObjectPosition?: string;
    collageAssets?: Array<{
      assetId: string;
      kind: 'image';
      publicFile: string;
      objectPosition?: string;
    }>;
    sourceStartMs: number;
    timelineStartMs: number;
    timelineEndMs: number;
    objectPosition?: string;
    presentation?: OverlayPresentation;
    motion?: OverlayMotion;
    headline?: string;
    kicker?: string;
    accentColor?: string;
    fadeIn?: boolean;
    fadeOut?: boolean;
  }>;
  effectCues?: EffectCue[];
  soundEffects?: SoundEffectCue[];
  captions: Array<{
    text: string;
    startMs: number;
    endMs: number;
    timestampMs: number | null;
    confidence: number | null;
    pageBreakAfter?: boolean;
  }>;
};

export const OverlayMedia: React.FC<{overlay: NonNullable<Job['overlays']>[number]}> = ({
  overlay,
}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const durationInFrames = Math.max(
    1,
    msToFrame(overlay.timelineEndMs - overlay.timelineStartMs, fps),
  );
  const progress = interpolate(frame, [0, durationInFrames], [0, 1], {
    easing: Easing.bezier(0.16, 1, 0.3, 1),
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  });
  const presentation = overlay.presentation ?? 'full';
  const motion = overlay.motion ?? 'push-in';
  const scale =
    motion === 'push-in'
      ? interpolate(progress, [0, 1], [1.025, 1.095], {output: 'perceptual-scale'})
      : motion === 'pull-out'
        ? interpolate(progress, [0, 1], [1.095, 1.025], {output: 'perceptual-scale'})
        : 1.055;
  const translate =
    motion === 'pan-left'
      ? `${interpolate(progress, [0, 1], [2.8, -2.8])}% 0%`
      : motion === 'pan-right'
        ? `${interpolate(progress, [0, 1], [-2.8, 2.8])}% 0%`
        : '0% 0%';
  const edgeFrames = Math.max(2, Math.min(Math.round(fps * 0.2), Math.floor(durationInFrames / 3)));
  const fadeInOpacity =
    overlay.fadeIn === false
      ? 1
      : interpolate(frame, [0, edgeFrames], [0, 1], {
          extrapolateLeft: 'clamp',
          extrapolateRight: 'clamp',
        });
  const fadeOutOpacity =
    overlay.fadeOut === false
      ? 1
      : interpolate(
          frame,
          [Math.max(edgeFrames, durationInFrames - edgeFrames), durationInFrames],
          [1, 0],
          {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'},
        );
  const opacity = Math.min(fadeInOpacity, fadeOutOpacity);
  const sharedStyle: React.CSSProperties = {
    height: '100%',
    objectFit: presentation === 'editorial' ? 'contain' : 'cover',
    objectPosition: overlay.objectPosition ?? '50% 50%',
    scale,
    translate,
    width: '100%',
  };

  const media = (
    source: {kind?: 'video' | 'image'; publicFile: string; sourceStartMs: number},
    style: React.CSSProperties,
  ) => {
    if (source.kind === 'image') {
      return <CanvasImage src={staticFile(source.publicFile)} style={style} />;
    }

    const {objectFit, ...videoStyle} = style;

    return (
      <Video
        muted
        objectFit={objectFit === 'contain' ? 'contain' : 'cover'}
        src={staticFile(source.publicFile)}
        trimBefore={msToFrame(source.sourceStartMs, fps)}
        style={videoStyle}
      />
    );
  };
  const primary = {
    kind: overlay.kind,
    publicFile: overlay.publicFile,
    sourceStartMs: overlay.sourceStartMs,
  };
  const secondary = overlay.secondaryPublicFile
    ? {
        kind: overlay.secondaryKind ?? undefined,
        publicFile: overlay.secondaryPublicFile,
        sourceStartMs: overlay.secondarySourceStartMs ?? 0,
      }
    : null;
  const accent = overlay.accentColor ?? '#ff174f';
  const title = overlay.headline?.trim();
  const kicker = overlay.kicker?.trim();
  const titleSize = Math.max(58, Math.min(112, 118 - Math.max(0, (title?.length ?? 0) - 12) * 1.7));

  const editorialText = title ? (
    <div
      style={{
        bottom: 145,
        color: '#fff',
        fontFamily: 'Arial, sans-serif',
        fontSize: titleSize,
        fontWeight: 950,
        left: 62,
        letterSpacing: '-0.055em',
        lineHeight: 0.88,
        position: 'absolute',
        right: 62,
        textShadow: '0 10px 34px rgba(0,0,0,.9)',
        textTransform: 'uppercase',
        translate: `0px ${interpolate(frame, [0, Math.max(1, fps * 0.42)], [56, 0], {
          easing: Easing.bezier(0.16, 1, 0.3, 1),
          extrapolateLeft: 'clamp',
          extrapolateRight: 'clamp',
        })}px`,
      }}
    >
      {kicker ? (
        <div
          style={{
            color: accent,
            fontSize: 28,
            letterSpacing: '0.16em',
            marginBottom: 18,
          }}
        >
          {kicker}
        </div>
      ) : null}
      {title}
      <div style={{backgroundColor: accent, height: 9, marginTop: 24, width: 150}} />
    </div>
  ) : null;

  if (presentation === 'paper-collage') {
    const collageSources = [
      {
        assetId: overlay.assetId ?? 'primary',
        kind: overlay.kind,
        objectPosition: overlay.objectPosition,
        publicFile: overlay.publicFile,
      },
      ...(overlay.collageAssets ?? []),
    ].slice(0, 3);
    const first = collageSources[0];
    const second = collageSources[1] ?? collageSources[0];
    const third = collageSources[2] ?? collageSources[1] ?? collageSources[0];
    const reveal = (start: number, end: number) =>
      interpolate(frame, [durationInFrames * start, durationInFrames * end], [0, 1], {
        easing: Easing.bezier(0.16, 1, 0.3, 1),
        extrapolateLeft: 'clamp',
        extrapolateRight: 'clamp',
      });
    const hide = (start: number, end: number) =>
      interpolate(frame, [durationInFrames * start, durationInFrames * end], [1, 0], {
        easing: Easing.bezier(0.7, 0, 0.84, 0),
        extrapolateLeft: 'clamp',
        extrapolateRight: 'clamp',
      });
    const firstIn = reveal(0.015, 0.1);
    const firstOut = hide(0.3, 0.37);
    const secondIn = reveal(0.31, 0.4);
    const secondOut = hide(0.51, 0.59);
    const fullIn = reveal(0.53, 0.61);
    const stripsIn = reveal(0.66, 0.75);
    const collageOut = hide(0.93, 1);
    const paperWords = [
      'SPORT',
      'BASKETBALL',
      'REPREZENTACJA',
      'MECZ',
      'POLSKA',
      'OLIMPIJSKI',
      'DRUŻYNA',
      'LIDER',
      'WYNIK',
      'ARENA',
      'TURNIEJ',
      'RAPORT',
    ];
    const tabColors = ['#e23059', '#10a8bd', '#e9a51d', '#295896', '#d94635'];
    const card = (
      source: (typeof collageSources)[number],
      cardOpacity: number,
      cardScale: number,
      cardTranslate: string,
      cardRotate: number,
    ) => (
      <div
        style={{
          backgroundColor: '#eee9dd',
          boxShadow: '0 28px 48px rgba(25,16,10,.48)',
          height: 990,
          left: 247,
          opacity: cardOpacity,
          padding: '28px 26px 108px',
          position: 'absolute',
          rotate: `${cardRotate}deg`,
          scale: cardScale,
          top: 350,
          translate: cardTranslate,
          width: 586,
          zIndex: 6,
        }}
      >
        <CanvasImage
          src={staticFile(source.publicFile)}
          style={{
            filter: 'contrast(1.04) saturate(.92)',
            height: '100%',
            objectFit: 'cover',
            objectPosition: source.objectPosition ?? '50% 50%',
            width: '100%',
          }}
        />
        <div
          style={{
            bottom: 42,
            color: '#17130f',
            fontFamily: 'Arial, sans-serif',
            fontSize: 25,
            fontWeight: 900,
            left: 0,
            letterSpacing: '.16em',
            position: 'absolute',
            right: 0,
            textAlign: 'center',
          }}
        >
          ADRIAN BOGUCKI
        </div>
      </div>
    );
    return (
      <AbsoluteFill
        style={{
          backgroundColor: '#d7cfbd',
          opacity: opacity * collageOut,
          overflow: 'hidden',
        }}
      >
        <AbsoluteFill
          style={{
            filter: 'sepia(.34) contrast(.88)',
            scale: interpolate(progress, [0, 1], [1.08, 1.01], {output: 'perceptual-scale'}),
          }}
        >
          {Array.from({length: 36}).map((_, index) => {
            const column = index % 6;
            const row = Math.floor(index / 6);
            return (
              <div
                key={index}
                style={{
                  background:
                    index % 3 === 0
                      ? 'linear-gradient(90deg,#bdb49f,#f0eadc 18%,#c8bfad 55%,#ede7d9)'
                      : 'linear-gradient(90deg,#e8e1d2,#b7ae9c 52%,#eee8dc)',
                  border: '1px solid rgba(63,53,42,.22)',
                  boxShadow: 'inset 8px 0 18px rgba(60,44,28,.12)',
                  color: 'rgba(32,27,22,.74)',
                  fontFamily: 'Georgia, serif',
                  height: 360,
                  left: column * 188 - 26,
                  overflow: 'hidden',
                  padding: '18px 12px',
                  position: 'absolute',
                  rotate: `${((index * 7) % 9) - 4}deg`,
                  top: row * 325 - 45,
                  width: 220,
                }}
              >
                <div style={{borderBottom: '4px double rgba(30,24,18,.55)', fontSize: 22, fontWeight: 900}}>
                  {paperWords[index % paperWords.length]}
                </div>
                <div style={{fontSize: 11, lineHeight: 1.08, marginTop: 9, textAlign: 'justify'}}>
                  REPREZENTACJA POLSKI WALCZY O KOLEJNY WYNIK. SPORTOWY RAPORT Z ARENY I GŁOS DRUŻYNY. MECZ, EMOCJE, RYWALIZACJA I NAJWAŻNIEJSZE AKCJE.
                </div>
                <div style={{background: 'rgba(45,39,31,.34)', height: 92, marginTop: 12}} />
              </div>
            );
          })}
        </AbsoluteFill>

        <AbsoluteFill style={{background: 'radial-gradient(circle,transparent 35%,rgba(42,30,17,.25) 100%)'}} />

        {Array.from({length: 58}).map((_, index) => {
          const side = index % 2 === 0 ? 1 : -1;
          const lane = Math.floor(index / 2) % 7;
          return (
            <div
              key={`tab-${index}`}
              style={{
                backgroundColor: tabColors[index % tabColors.length],
                height: 38 + ((index * 13) % 34),
                left: side > 0 ? 805 + lane * 28 : 210 - lane * 28,
                opacity: 0.9 * reveal(0.05 + (index % 8) * 0.006, 0.14 + (index % 8) * 0.006),
                position: 'absolute',
                rotate: `${((index * 11) % 17) - 8}deg`,
                top: 230 + ((index * 83) % 1390),
                width: 42 + ((index * 17) % 42),
                zIndex: 3,
              }}
            />
          );
        })}

        {card(
          first,
          firstIn * firstOut,
          interpolate(firstIn, [0, 1], [1.34, 0.92], {output: 'perceptual-scale'}),
          `0px ${interpolate(firstIn, [0, 1], [520, 0])}px`,
          -1.2,
        )}
        {card(
          second,
          secondIn * secondOut,
          interpolate(secondIn, [0, 1], [0.78, 1.02], {output: 'perceptual-scale'}),
          `${interpolate(secondIn, [0, 1], [600, 0])}px ${interpolate(secondIn, [0, 1], [80, 0])}px`,
          1.1,
        )}

        <AbsoluteFill
          style={{
            opacity: fullIn * hide(0.72, 0.78),
            overflow: 'hidden',
            scale: interpolate(fullIn, [0, 1], [0.72, 1.13], {output: 'perceptual-scale'}),
            zIndex: 9,
          }}
        >
          <CanvasImage
            src={staticFile(third.publicFile)}
            style={{
              filter: `brightness(${interpolate(fullIn, [0, 1], [2.1, 1])}) contrast(1.05)`,
              height: '100%',
              objectFit: 'cover',
              objectPosition: third.objectPosition ?? '50% 50%',
              width: '100%',
            }}
          />
        </AbsoluteFill>

        <AbsoluteFill style={{opacity: stripsIn, overflow: 'hidden', zIndex: 10}}>
          {[
            {clip: 'polygon(0 0,37% 0,30% 100%,0 100%)', source: first, x: '-3%'},
            {clip: 'polygon(34% 0,72% 0,66% 100%,27% 100%)', source: third, x: '0%'},
            {clip: 'polygon(69% 0,100% 0,100% 100%,63% 100%)', source: second, x: '3%'},
          ].map((strip, index) => (
            <AbsoluteFill
              key={`strip-${strip.source.assetId}-${index}`}
              style={{
                clipPath: strip.clip,
                translate: `${interpolate(stripsIn, [0, 1], [index === 1 ? 0 : index === 0 ? -230 : 230, 0])}px 0px`,
              }}
            >
              <CanvasImage
                src={staticFile(strip.source.publicFile)}
                style={{
                  filter: index === 1 ? 'none' : 'saturate(.84) contrast(1.08)',
                  height: '100%',
                  objectFit: 'cover',
                  objectPosition: strip.source.objectPosition ?? '50% 50%',
                  translate: `${strip.x} 0%`,
                  width: '106%',
                }}
              />
              <AbsoluteFill
                style={{
                  background:
                    index === 0
                      ? 'linear-gradient(90deg,transparent 89%,rgba(249,245,235,.96) 90%,rgba(249,245,235,.96) 94%,transparent 95%)'
                      : 'linear-gradient(90deg,rgba(249,245,235,.96) 4%,transparent 6%)',
                }}
              />
            </AbsoluteFill>
          ))}
          <AbsoluteFill
            style={{
              background:
                'repeating-linear-gradient(174deg,transparent 0px,transparent 135px,rgba(246,242,233,.88) 137px,rgba(246,242,233,.88) 143px,transparent 146px)',
              opacity: reveal(0.72, 0.79),
            }}
          />
        </AbsoluteFill>

        <AbsoluteFill
          style={{
            backgroundColor: '#fffdf4',
            opacity:
              interpolate(frame, [0, durationInFrames * 0.035, durationInFrames * 0.08], [0.95, 0.95, 0], {
                extrapolateLeft: 'clamp',
                extrapolateRight: 'clamp',
              }) +
              interpolate(
                frame,
                [durationInFrames * 0.51, durationInFrames * 0.55, durationInFrames * 0.61],
                [0, 0.78, 0],
                {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'},
              ),
            zIndex: 20,
          }}
        />
        <AbsoluteFill
          style={{
            background: 'linear-gradient(180deg, transparent 64%, rgba(0,0,0,.34) 100%)',
            zIndex: 21,
          }}
        />
      </AbsoluteFill>
    );
  }

  if ((presentation === 'split' || presentation === 'stack') && secondary) {
    if (presentation === 'split') {
      return (
        <AbsoluteFill style={{backgroundColor: '#050505', opacity, overflow: 'hidden'}}>
          <div
            style={{
              bottom: 0,
              clipPath: 'polygon(0 0, 100% 0, 88% 100%, 0 100%)',
              left: 0,
              overflow: 'hidden',
              position: 'absolute',
              top: 0,
              translate: `${interpolate(frame, [0, Math.max(1, fps * 0.38)], [-18, 0], {
                easing: Easing.bezier(0.16, 1, 0.3, 1),
                extrapolateLeft: 'clamp',
                extrapolateRight: 'clamp',
              })}% 0%`,
              width: '57%',
            }}
          >
            {media(primary, {...sharedStyle, objectFit: 'cover'})}
          </div>
          <div
            style={{
              bottom: 0,
              clipPath: 'polygon(13% 0, 100% 0, 100% 100%, 0 100%)',
              overflow: 'hidden',
              position: 'absolute',
              right: 0,
              top: 0,
              translate: `${interpolate(frame, [0, Math.max(1, fps * 0.38)], [18, 0], {
                easing: Easing.bezier(0.16, 1, 0.3, 1),
                extrapolateLeft: 'clamp',
                extrapolateRight: 'clamp',
              })}% 0%`,
              width: '57%',
            }}
          >
            {media(secondary, {
              ...sharedStyle,
              objectFit: 'cover',
              objectPosition: overlay.secondaryObjectPosition ?? '50% 50%',
            })}
          </div>
          <div
            style={{
              backgroundColor: accent,
              height: '118%',
              left: '49.5%',
              opacity: 0.88,
              position: 'absolute',
              rotate: '3.5deg',
              top: '-9%',
              width: 7,
            }}
          />
          <AbsoluteFill
            style={{background: 'linear-gradient(180deg, transparent 48%, rgba(0,0,0,.72) 100%)'}}
          />
          {editorialText}
        </AbsoluteFill>
      );
    }

    return (
      <AbsoluteFill style={{backgroundColor: '#090707', opacity, overflow: 'hidden'}}>
        {media(primary, {
          ...sharedStyle,
          filter: 'blur(38px) brightness(.34) saturate(.65)',
          objectFit: 'cover',
          scale: scale * 1.18,
        })}
        <AbsoluteFill
          style={{
            background: `radial-gradient(circle at 50% 38%, ${accent}33 0%, transparent 48%), linear-gradient(160deg, #050505 10%, transparent 55%, #050505 100%)`,
          }}
        />
        <div
          style={{
            height: '54%',
            left: 56,
            overflow: 'hidden',
            position: 'absolute',
            rotate: '-4deg',
            top: 120,
            translate: `${interpolate(frame, [0, Math.max(1, fps * 0.46)], [-100, 0], {
              easing: Easing.bezier(0.16, 1, 0.3, 1),
              extrapolateLeft: 'clamp',
              extrapolateRight: 'clamp',
            })}px 0px`,
            width: '66%',
          }}
        >
          {media(primary, {...sharedStyle, objectFit: 'cover'})}
        </div>
        <div
          style={{
            border: '8px solid rgba(255,255,255,.92)',
            bottom: 250,
            boxShadow: '0 28px 70px rgba(0,0,0,.68)',
            height: '46%',
            overflow: 'hidden',
            position: 'absolute',
            right: 48,
            rotate: '4.5deg',
            translate: `${interpolate(frame, [0, Math.max(1, fps * 0.52)], [110, 0], {
              easing: Easing.bezier(0.16, 1, 0.3, 1),
              extrapolateLeft: 'clamp',
              extrapolateRight: 'clamp',
            })}px 0px`,
            width: '62%',
          }}
        >
          {media(secondary, {
            ...sharedStyle,
            objectFit: 'cover',
            objectPosition: overlay.secondaryObjectPosition ?? '50% 50%',
          })}
        </div>
        {editorialText}
      </AbsoluteFill>
    );
  }

  if (presentation === 'cutout') {
    return (
      <AbsoluteFill style={{backgroundColor: '#050505', opacity, overflow: 'hidden'}}>
        <AbsoluteFill
          style={{
            background: `radial-gradient(circle at 52% 42%, ${accent}52 0%, ${accent}12 34%, transparent 68%)`,
          }}
        />
        {title ? (
          <div
            style={{
              color: 'rgba(255,255,255,.09)',
              fontFamily: 'Arial, sans-serif',
              fontSize: Math.min(190, titleSize * 1.62),
              fontWeight: 950,
              left: -20,
              letterSpacing: '-0.08em',
              lineHeight: 0.78,
              position: 'absolute',
              right: -20,
              textAlign: 'center',
              textTransform: 'uppercase',
              top: 170,
            }}
          >
            {title}
          </div>
        ) : null}
        {media(primary, {
          ...sharedStyle,
          filter: `drop-shadow(0 28px 48px rgba(0,0,0,.9)) drop-shadow(0 0 18px ${accent}55)`,
          objectFit: 'contain',
          scale: scale * 0.94,
        })}
        <AbsoluteFill
          style={{background: 'linear-gradient(180deg, transparent 58%, rgba(0,0,0,.78) 100%)'}}
        />
        {editorialText}
      </AbsoluteFill>
    );
  }

  if (presentation === 'editorial') {
    return (
      <AbsoluteFill style={{backgroundColor: '#050505', opacity, overflow: 'hidden'}}>
        {media(primary, {
          ...sharedStyle,
          filter: 'blur(34px) saturate(.72) brightness(.48)',
          objectFit: 'cover',
          opacity: 0.86,
          scale: scale * 1.16,
        })}
        <AbsoluteFill
          style={{
            background:
              'radial-gradient(circle at 50% 42%, transparent 30%, rgba(0,0,0,.62) 100%)',
          }}
        />
        <div
          style={{
            bottom: 92,
            boxShadow: '0 28px 90px rgba(0,0,0,.72)',
            left: 44,
            overflow: 'hidden',
            position: 'absolute',
            right: 44,
            top: 92,
          }}
        >
          {media(primary, {...sharedStyle, objectFit: 'contain'})}
        </div>
        {editorialText}
      </AbsoluteFill>
    );
  }

  return (
    <AbsoluteFill style={{backgroundColor: '#000', opacity, overflow: 'hidden'}}>
      {media(primary, {
        ...sharedStyle,
        filter:
          presentation === 'archive'
            ? 'grayscale(.96) contrast(1.12) brightness(.9)'
            : 'none',
      })}
      {presentation === 'archive' ? (
        <AbsoluteFill
          style={{
            background:
              'repeating-linear-gradient(0deg, rgba(255,255,255,.026) 0px, rgba(255,255,255,.026) 1px, transparent 1px, transparent 4px), radial-gradient(circle at 50% 45%, transparent 46%, rgba(0,0,0,.72) 100%)',
            boxShadow: 'inset 0 0 0 3px rgba(255,255,255,.42)',
            margin: 38,
            opacity: 0.82,
          }}
        />
      ) : null}
      {editorialText}
    </AbsoluteFill>
  );
};

const job = rawJob as Job;

const msToFrame = (milliseconds: number, fps: number) =>
  Math.round((milliseconds / 1000) * fps);

const ZOOM_MULTIPLIERS: Record<ZoomLevel, number> = {
  wide: 1,
  medium: 1.15,
  close: 1.2,
};

const EditedClip: React.FC<{edit: Job['edits'][number]}> = ({edit}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const durationInFrames = Math.max(
    1,
    msToFrame(edit.timelineEndMs - edit.timelineStartMs, fps),
  );
  const scaleFrom = edit.scaleFrom ?? 1;
  const scaleTo = edit.scaleTo ?? scaleFrom;
  const globalMs = edit.timelineStartMs + (frame / fps) * 1000;
  const beats = job.visualBeats ?? [];
  const matchingBeatIndex = beats.findIndex(
    (beat) => globalMs >= beat.timelineStartMs && globalMs < beat.timelineEndMs,
  );
  const beatIndex = matchingBeatIndex >= 0 ? matchingBeatIndex : Math.max(0, beats.length - 1);
  const beat = beats[beatIndex];
  const previousBeat = beats[Math.max(0, beatIndex - 1)];
  const currentMultiplier = beat ? ZOOM_MULTIPLIERS[beat.zoomLevel] : 1;
  const previousMultiplier = previousBeat
    ? ZOOM_MULTIPLIERS[previousBeat.zoomLevel]
    : currentMultiplier;
  const transitionFrame = beat
    ? ((globalMs - beat.timelineStartMs) / 1000) * fps
    : Number.POSITIVE_INFINITY;
  const beatDurationFrames = beat
    ? Math.max(1, ((beat.timelineEndMs - beat.timelineStartMs) / 1000) * fps)
    : fps;
  const transitionFrames = Math.max(
    1,
    Math.round(Math.min(fps * 0.64, beatDurationFrames * 0.58)),
  );
  const effectPulse =
    beatIndex > 0 && beat?.transitionEffect !== 'smooth'
      ? interpolate(
          transitionFrame,
          [0, transitionFrames / 2, transitionFrames],
          [0, 1, 0],
          {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'},
        )
      : 0;
  const zoomDirection = currentMultiplier >= previousMultiplier ? 1 : -1;
  const transitionEffects =
    beatIndex === 0 || effectPulse <= 0
      ? []
      : beat?.transitionEffect === 'blur'
        ? [
            zoomBlur({
              amount: effectPulse * 22,
              center: [0.5, 0.4],
              samples: 28,
            }),
          ]
        : beat?.transitionEffect === 'rgb'
          ? [
              chromaticAberration({
                amount: effectPulse * 4.2,
                angle: zoomDirection > 0 ? 0 : 180,
              }),
            ]
          : [];
  const grade = job.colorGrade ?? {
    contrast: 1,
    saturation: 1,
    brightness: 1,
    sepia: 0,
  };

  return (
    <AbsoluteFill style={{overflow: 'hidden'}}>
      <AbsoluteFill style={{translate: edit.translate ?? '0px 0px'}}>
        <AbsoluteFill
          style={{
            scale:
              interpolate(
                transitionFrame,
                [0, transitionFrames * 0.68, transitionFrames],
                [
                  scaleFrom * previousMultiplier,
                  scaleTo * currentMultiplier + zoomDirection * 0.012,
                  scaleTo * currentMultiplier,
                ],
                {
                  easing: Easing.bezier(0.16, 1, 0.3, 1),
                  extrapolateLeft: 'clamp',
                  extrapolateRight: 'clamp',
                  output: 'perceptual-scale',
                },
              ) +
              interpolate(
                transitionFrame,
                [transitionFrames, beatDurationFrames],
                [0, 0.006],
                {
                  extrapolateLeft: 'clamp',
                  extrapolateRight: 'clamp',
                  output: 'perceptual-scale',
                },
              ),
          }}
        >
          <Video
            effects={transitionEffects}
            objectFit="cover"
            src={staticFile(job.source.publicFile)}
            trimBefore={msToFrame(edit.sourceStartMs, fps)}
            style={{
              filter: `brightness(${grade.brightness}) contrast(${grade.contrast * (1 + effectPulse * 0.04)}) saturate(${grade.saturation * (1 + effectPulse * 0.09)}) sepia(${grade.sepia})`,
              height: '100%',
              left: 0,
              objectPosition: edit.objectPosition ?? '50% 50%',
              opacity: 1,
              position: 'absolute',
              top: 0,
              width: '100%',
            }}
          />
          {effectPulse > 0 && beat?.transitionEffect === 'split' ? (
            <>
              <Video
                muted
                objectFit="cover"
                src={staticFile(job.source.publicFile)}
                trimBefore={msToFrame(edit.sourceStartMs, fps)}
                style={{
                  height: '100%',
                  left: 0,
                  maskImage:
                    'linear-gradient(to bottom, #000 0%, #000 27%, transparent 38%)',
                  objectPosition: edit.objectPosition ?? '50% 50%',
                  opacity: effectPulse * 0.4,
                  position: 'absolute',
                  top: 0,
                  filter: `blur(${effectPulse * 1.5}px)`,
                  translate: `${effectPulse * -9}px 0px`,
                  width: '100%',
                }}
              />
              <Video
                muted
                objectFit="cover"
                src={staticFile(job.source.publicFile)}
                trimBefore={msToFrame(edit.sourceStartMs, fps)}
                style={{
                  height: '100%',
                  left: 0,
                  maskImage:
                    'linear-gradient(to bottom, transparent 27%, #000 39%, #000 61%, transparent 73%)',
                  objectPosition: edit.objectPosition ?? '50% 50%',
                  opacity: effectPulse * 0.42,
                  position: 'absolute',
                  top: 0,
                  filter: `blur(${effectPulse * 1.5}px)`,
                  translate: `${effectPulse * 10}px 0px`,
                  width: '100%',
                }}
              />
              <Video
                muted
                objectFit="cover"
                src={staticFile(job.source.publicFile)}
                trimBefore={msToFrame(edit.sourceStartMs, fps)}
                style={{
                  filter: `blur(${effectPulse * 1.2}px)`,
                  height: '100%',
                  left: 0,
                  maskImage:
                    'linear-gradient(to bottom, transparent 62%, #000 73%, #000 100%)',
                  objectPosition: edit.objectPosition ?? '50% 50%',
                  opacity: effectPulse * 0.36,
                  position: 'absolute',
                  top: 0,
                  translate: `${effectPulse * -7}px 0px`,
                  width: '100%',
                }}
              />
            </>
          ) : null}
          {effectPulse > 0 ? (
            <AbsoluteFill
              style={{
                background:
                  'radial-gradient(circle at 50% 40%, transparent 42%, rgba(0,0,0,.5) 100%)',
                mixBlendMode: 'multiply',
                opacity: effectPulse * 0.2,
              }}
            />
          ) : null}
        </AbsoluteFill>
      </AbsoluteFill>
    </AbsoluteFill>
  );
};

export const BaronReel = () => {
  const {fps} = useVideoConfig();

  // A-roll i przebitki (B-roll/IMAGE) leżą na osobnych warstwach i mogą się nakładać
  // (przebitki kładą się na prowadzącym). Sanitizer minimalnej długości działa więc
  // oddzielnie na każdej osi, żeby nie scalał ze sobą różnych typów treści.
  const aRollScenes: Scene[] = (job.edits ?? []).map((edit) => ({
    type: 'A_ROLL',
    startFrame: msToFrame(edit.timelineStartMs, fps),
    endFrame: msToFrame(edit.timelineEndMs, fps),
  }));
  const bRollScenes: Scene[] = (job.overlays ?? []).map((overlay) => ({
    type: overlay.kind === 'image' ? 'IMAGE' : 'B_ROLL',
    src: overlay.publicFile,
    startFrame: msToFrame(overlay.timelineStartMs, fps),
    endFrame: msToFrame(overlay.timelineEndMs, fps),
  }));

  const sanitizedARoll =
    sanitizeTimeline([...aRollScenes].sort((x, y) => x.startFrame - y.startFrame), fps, 3.0);
  const sanitizedBRoll =
    sanitizeTimeline([...bRollScenes].sort((x, y) => x.startFrame - y.startFrame), fps, 3.0);

  // Identyfikatory zachowane po sanityzacji (do filtrowania renderowanych elementów).
  const keptARollFrames = sanitizedARoll
    .filter((s) => s.type === 'A_ROLL')
    .map((s) => [s.startFrame, s.endFrame] as [number, number]);
  const keptBrollStartFrames = sanitizedBRoll
    .filter((s) => s.type !== 'A_ROLL')
    .map((s) => s.startFrame);

  const aRollEditIds = (job.edits ?? [])
    .filter((edit) => {
      const f = msToFrame(edit.timelineStartMs, fps);
      return keptARollFrames.some(([s, e]) => f >= s && f < e);
    })
    .map((edit) => edit.id);
  const bRollIds = (job.overlays ?? [])
    .filter((overlay) => {
      const f = msToFrame(overlay.timelineStartMs, fps);
      return keptBrollStartFrames.some((sf) => f === sf);
    })
    .map((overlay) => overlay.id);

  return (
    <AbsoluteFill style={{backgroundColor: '#000000'}}>
      {job.edits.map((edit) => (
        <Sequence
          key={edit.id}
          from={msToFrame(edit.timelineStartMs, fps)}
          durationInFrames={Math.max(
            1,
            msToFrame(edit.timelineEndMs - edit.timelineStartMs, fps),
          )}
          premountFor={fps}
        >
          {aRollEditIds.includes(edit.id) ? <EditedClip edit={edit} /> : null}
        </Sequence>
      ))}

      {(job.overlays ?? []).map((overlay) => (
        <Sequence
          key={overlay.id}
          from={msToFrame(overlay.timelineStartMs, fps)}
          durationInFrames={Math.max(
            1,
            msToFrame(overlay.timelineEndMs - overlay.timelineStartMs, fps),
          )}
          premountFor={fps}
        >
          {bRollIds.includes(overlay.id) ? (
            <OverlayMedia overlay={overlay} />
          ) : null}
        </Sequence>
      ))}

      <EffectLayer cues={job.effectCues ?? []} />
      <SoundEffects cues={job.soundEffects ?? []} />

      <WordCaptions
        captions={job.captions}
        styleMode={job.captionStyle ?? 'green-word'}
      />
    </AbsoluteFill>
  );
};
