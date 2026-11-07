import {createTikTokStyleCaptions, type Caption, type TikTokPage} from '@remotion/captions';
import {AbsoluteFill, Sequence, useCurrentFrame, useVideoConfig} from 'remotion';
import type {CaptionStyle} from './BaronReel';

// Page boundaries are prepared by the local pipeline: at most three words,
// always after punctuation and at every edit boundary. The large duration
// prevents the library from inserting an additional time-based split.
const PAGE_GROUPING_WINDOW_MS = 60_000;
const CAPTION_TAIL_MS = 160;
const ACTIVE_BACKGROUND = '#39E508';

const CaptionPage: React.FC<{page: TikTokPage; styleMode: CaptionStyle}> = ({
  page,
  styleMode,
}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const absoluteTimeMs = page.startMs + (frame / fps) * 1000;
  const whiteOutline = styleMode === 'white-outline';

  return (
    <AbsoluteFill style={{pointerEvents: 'none'}}>
      <div
        style={{
          color: '#ffffff',
          fontFamily: 'Arial Black, Arial, sans-serif',
          fontSize: 66,
          fontWeight: 900,
          left: 72,
          lineHeight: 1.16,
          position: 'absolute',
          right: 72,
          textAlign: 'center',
          textShadow: whiteOutline
            ? '-3px -3px 0 #000, 3px -3px 0 #000, -3px 3px 0 #000, 3px 3px 0 #000, 0 5px 12px rgba(0,0,0,0.9)'
            : '0 4px 12px rgba(0,0,0,0.95)',
          textTransform: whiteOutline ? 'uppercase' : 'none',
          top: 1320,
          whiteSpace: 'pre-wrap',
        }}
      >
        {page.tokens.map((token) => {
          const active = token.fromMs <= absoluteTimeMs && token.toMs > absoluteTimeMs;
          const leadingWhitespace = token.text.match(/^\s*/)?.[0] ?? '';
          const word = token.text.slice(leadingWhitespace.length);
          return (
            <span key={`${token.fromMs}-${token.toMs}-${token.text}`}>
              {leadingWhitespace}
              <span
                style={{
                  backgroundColor:
                    !whiteOutline && active ? ACTIVE_BACKGROUND : 'transparent',
                  borderRadius: !whiteOutline && active ? 3 : 0,
                  color: '#ffffff',
                  padding: !whiteOutline && active ? '1px 3px' : 0,
                  textShadow:
                    !whiteOutline && active
                      ? '-1px -1px 0 #000, 1px -1px 0 #000, -1px 1px 0 #000, 1px 1px 0 #000, 0 4px 12px rgba(0,0,0,0.95)'
                      : 'inherit',
                }}
              >
                {word}
              </span>
            </span>
          );
        })}
      </div>
    </AbsoluteFill>
  );
};

export const WordCaptions: React.FC<{
  captions: Caption[];
  styleMode: CaptionStyle;
}> = ({captions, styleMode}) => {
  const {fps} = useVideoConfig();
  const {pages} = createTikTokStyleCaptions({
    captions,
    combineTokensWithinMilliseconds: PAGE_GROUPING_WINDOW_MS,
  });

  return (
    <AbsoluteFill>
      {pages.map((page, index) => {
        const nextPage = pages[index + 1];
        const startFrame = Math.round((page.startMs / 1000) * fps);
        const lastToken = page.tokens.at(-1);
        const naturalEndMs = (lastToken?.toMs ?? page.startMs) + CAPTION_TAIL_MS;
        const endMs = nextPage ? Math.min(nextPage.startMs, naturalEndMs) : naturalEndMs;
        const endFrame = Math.round((endMs / 1000) * fps);
        let durationInFrames = endFrame - startFrame;
        if (durationInFrames <= 0) {
          // Robustność: zamiast gubić stronę napisów (np. przez 1-klatkowe
          // słowo), pokaż ją przez pojedynczą klatkę.
          durationInFrames = 1;
        }
        return (
          <Sequence
            key={`${page.startMs}-${index}`}
            from={startFrame}
            durationInFrames={durationInFrames}
            premountFor={fps}
          >
            <CaptionPage page={page} styleMode={styleMode} />
          </Sequence>
        );
      })}
    </AbsoluteFill>
  );
};
