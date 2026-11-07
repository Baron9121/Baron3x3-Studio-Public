import {AbsoluteFill, Easing, interpolate, useCurrentFrame} from 'remotion';

export const SmokeTest = () => {
  const frame = useCurrentFrame();

  return (
    <AbsoluteFill
      style={{
        alignItems: 'center',
        backgroundColor: '#0b0b0b',
        color: '#ffffff',
        display: 'flex',
        fontFamily: 'Arial, sans-serif',
        justifyContent: 'center',
      }}
    >
      <div
        style={{
          fontSize: 92,
          fontWeight: 800,
          opacity: interpolate(frame, [0, 20], [0, 1], {
            easing: Easing.bezier(0.16, 1, 0.3, 1),
            extrapolateLeft: 'clamp',
            extrapolateRight: 'clamp',
          }),
          textAlign: 'center',
        }}
      >
        Baron3x3
        <div style={{color: '#ffcc00', fontSize: 52, marginTop: 24}}>
          Remotion działa lokalnie
        </div>
      </div>
    </AbsoluteFill>
  );
};
