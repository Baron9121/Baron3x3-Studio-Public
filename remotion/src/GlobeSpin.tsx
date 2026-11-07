import {AbsoluteFill, Easing, interpolate, useCurrentFrame, useVideoConfig} from 'remotion';

// Lokalna animacja „kula ziemska” (runda 2; bez płatnego modelu graficznego).
// Obrót wokół osi, zarysy kontynentów, pinezka na Hongcheon (Korea) i przybliżenie.

const worldLon = 1600;
const world = (longitude: number, latitude: number) =>
  `${((longitude + 180) / 360) * worldLon} ${((85 - latitude) / 170) * 800}`;
const poly = (pts: Array<[number, number]>) => pts.map(([lon, lat]) => world(lon, lat)).join(' ');

const CONTINENTS = [
  poly([[-168, 70], [-160, 60], [-124, 49], [-118, 34], [-105, 30], [-97, 26], [-83, 22], [-80, 31], [-75, 45], [-55, 50], [-70, 48], [-70, 60], [-80, 68], [-100, 72], [-140, 72], [-168, 70]]),
  poly([[-78, 10], [-70, 12], [-62, 5], [-58, -10], [-70, -15], [-75, -35], [-68, -45], [-64, -55], [-70, -55], [-73, -40], [-76, -20], [-80, -3], [-82, 6]]),
  poly([[-10, 36], [5, 43], [25, 45], [40, 55], [55, 70], [72, 73], [98, 76], [120, 73], [140, 72], [160, 60], [178, 66], [170, 55], [150, 42], [134, 33], [118, 31], [112, 23], [100, 17], [88, 12], [72, 16], [55, 22], [45, 12], [38, 30], [30, 37], [25, 40], [18, 44], [10, 60], [40, 72], [-10, 64], [-18, 48], [-10, 36]]),
  poly([[-10, 36], [10, 35], [20, 32], [37, 33], [45, 25], [50, 12], [55, 8], [40, 5], [32, -10], [18, -35], [10, -35], [0, -5], [-15, 15], [-17, 18], [-10, 36]]),
  poly([[115, -25], [128, -14], [145, -11], [153, -25], [147, -38], [138, -35], [126, -34], [119, -26]]),
  poly([[-110, -75], [-70, -72], [-30, -70], [20, -70], [60, -70], [100, -70], [140, -72], [170, -74], [180, -70]]),
];

const hongcheonPx = ((127.9 + 180) / 360) * worldLon;
const koreaY = ((85 - 37.7) / 170) * 800;

export const GlobeSpin: React.FC = () => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const t = frame / fps;

  const rotation = interpolate(t, [0, 2.0], [0, 720], {easing: Easing.bezier(0.3, 0.1, 0.4, 1), extrapolateRight: 'clamp'});
  const pinIn = interpolate(t, [2.35, 3.0], [0, 1], {easing: Easing.out(Easing.cubic), extrapolateRight: 'clamp'});
  const zoom = interpolate(t, [3.0, 4.5], [1, 2.8], {easing: Easing.bezier(0.5, 0, 0.6, 1), extrapolateRight: 'clamp'});
  const panX = interpolate(t, [3.0, 4.8], [0, -170], {easing: Easing.bezier(0.5, 0, 0.6, 1), extrapolateRight: 'clamp'});
  const panY = interpolate(t, [3.0, 4.8], [0, -40], {easing: Easing.bezier(0.5, 0, 0.6, 1), extrapolateRight: 'clamp'});
  const labelCountry = interpolate(t, [4.1, 4.7], [0, 1], {easing: Easing.out(Easing.cubic), extrapolateRight: 'clamp'});
  const labelCity = interpolate(t, [4.8, 5.35], [0, 1], {easing: Easing.out(Easing.cubic), extrapolateRight: 'clamp'});
  const titleOpacity = interpolate(t, [0.15, 0.55], [0, 0.9], {extrapolateRight: 'clamp'});
  const fadeOut = 1 - interpolate(t, [5.45, 5.95], [0, 1], {extrapolateLeft: 'clamp'});

  const W = 1080;
  const H = 1920;
  const sphere = 900;
  const cx = W / 2 - panX;
  const cy = H / 2 - 120 + panY;

  return (
    <AbsoluteFill style={{backgroundColor: '#04060d'}}>
      <div
        style={{
          position: 'absolute',
          left: 0,
          top: 0,
          width: W,
          height: H,
          background:
            'radial-gradient(circle at 50% 42%, #0e1c33 0%, #060c18 34%, #02040a 100%)',
        }}
      />
      <div
        style={{
          position: 'absolute',
          left: 0,
          top: 120,
          width: W,
          color: '#cfe0ff',
          fontFamily: 'Arial, sans-serif',
          fontSize: 52,
          fontWeight: 800,
          letterSpacing: '0.2em',
          textAlign: 'center',
          opacity: titleOpacity * (1 - zoom * 0.35),
        }}
      >
        KOLEJNA OKAZJA
      </div>
      <div
        style={{
          position: 'absolute',
          left: cx - sphere / 2,
          top: cy - (sphere / 2),
          width: sphere,
          height: sphere,
          borderRadius: '50%',
          overflow: 'hidden',
          background: 'radial-gradient(circle at 33% 30%, rgba(70,110,190,.24), rgba(10,22,48,.96) 62%, #04070c 78%)',
          boxShadow: '0 0 0 6px rgba(120,160,230,.18), 0 130px 280px rgba(0,0,0,.85)',
          scale: `${zoom * fadeOut}`,
          transformStyle: 'preserve-3d',
          rotateY: `${rotation}deg`,
        }}
      >
        <svg
          width={worldLon}
          height={800}
          viewBox={`0 0 ${worldLon} 800`}
          style={{position: 'absolute', left: -worldLon / 2, top: 800 / 2 - sphere / 2, width: worldLon, height: 800}}
        >
          <g fill="rgba(26,60,110,.72)" stroke="rgba(150,190,240,.92)" strokeWidth={2.6}>
            {CONTINENTS.map((d) => <polygon key={d} points={d} />)}
          </g>
          <g stroke="rgba(90,140,220,.25)" strokeWidth={1}>
            {[-120, -60, 0, 60, 120].map((lon) => (
              <line key={`l${lon}`} x1={((lon + 180) / 360) * worldLon} y1={0} x2={((lon + 180) / 360) * worldLon} y2={800} />
            ))}
            {[-40, 0, 40].map((lat) => (
              <line key={`a${lat}`} x1={0} y1={((85 - lat) / 170) * 800} x2={worldLon} y2={((85 - lat) / 170) * 800} />
            ))}
          </g>
        </svg>
      </div>
      <div
        style={{
          position: 'absolute',
          left: cx + (hongcheonPx - worldLon / 2) * zoom - 46,
          top: cy + (koreaY - 400) * zoom - 46,
          width: 92,
          height: 92,
          borderRadius: '50%',
          opacity: pinIn,
          background: 'radial-gradient(circle, #ff174f 55%, rgba(255,23,79,.3) 100%)',
          boxShadow: '0 0 34px rgba(255,23,79,.75)',
        }}
      >
        <div
          style={{
            position: 'absolute',
            left: 32,
            top: 30,
            width: 28,
            height: 32,
            color: '#fff',
            fontSize: 15,
            textAlign: 'center',
            lineHeight: '16px',
          }}
        >
          H
        </div>
      </div>
      <div
        style={{
          position: 'absolute',
          left: 0,
          top: 1180,
          width: W,
          color: '#ffffff',
          fontFamily: 'Arial, sans-serif',
          fontSize: 64,
          fontWeight: 950,
          textAlign: 'center',
          opacity: labelCountry,
          textShadow: '0 8px 30px rgba(0,0,0,.9)',
        }}
      >
        KOREA POŁUDNIOWA
      </div>
      <div
        style={{
          position: 'absolute',
          left: 0,
          top: 1300,
          width: W,
          color: '#ff174f',
          fontFamily: 'Arial, sans-serif',
          fontSize: 74,
          fontWeight: 950,
          textAlign: 'center',
          opacity: labelCity,
          textShadow: '0 8px 30px rgba(0,0,0,.9)',
        }}
      >
        HONGCHEON • 18–19 WRZEŚNIA
      </div>
    </AbsoluteFill>
  );
};