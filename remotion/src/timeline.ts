export interface Scene {
  type: 'A_ROLL' | 'B_ROLL' | 'IMAGE';
  src?: string;
  startFrame: number;
  endFrame: number;
}

export const msToFrame = (ms: number, fps: number): number =>
  Math.round((ms / 1000) * fps);

/**
 * Wymusza minimalną długość sceny w kadrach.
 * Podczas gdy walidator Python (preview_qa) tylko FAILUJE przy scenie krótszej niż
 * minimum, ten sanitizer działa na etapie renderu: scala zbyt krótki kadr z poprzednim.
 */
export const sanitizeTimeline = (
  scenes: Scene[],
  fps = 30,
  minDurationSec = 3.0,
): Scene[] => {
  const minFrames = minDurationSec * fps;
  const cleaned: Scene[] = [];

  for (let i = 0; i < scenes.length; i++) {
    const current = {...scenes[i]};
    const duration = current.endFrame - current.startFrame;

    // Jeśli kadr trwa krócej niż 3 sekundy (90 klatek przy 30 fps)
    if (duration < minFrames) {
      if (cleaned.length > 0) {
        // Połącz za krótki kadr z poprzednią sceną (rozciągnij poprzednią)
        cleaned[cleaned.length - 1].endFrame = current.endFrame;
      } else if (i + 1 < scenes.length) {
        // Jeśli to pierwsza scena, rozciągnij ją kosztem następnej
        scenes[i + 1].startFrame = current.startFrame;
      }
    } else {
      cleaned.push(current);
    }
  }

  return cleaned;
};