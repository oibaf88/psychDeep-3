/**
 * Urge-surfing surface for Regular (/wave).
 *
 * The drawing stays a stack of traveling curves. What changes is the motion
 * those curves ride on:
 *
 * - One shared breath lifts and drops the whole surface. The rise is the
 *   shorter part of the cycle and accelerates into the crest; the fall is
 *   longer and decelerates. Peak versus trough is that vertical travel,
 *   not a second slider event.
 * - Intensity retunes the same breath. Higher urge shortens the cycle,
 *   packs in more crests, leans them (sharper faces), and speeds the
 *   travel — most of all while the breath is high. The trough of a strong
 *   urge lets the texture loosen again, so the fall reads as relief.
 * - Low urge keeps the same rise and fall, but slow, round, and widely spaced.
 */

export const WAVE_WIDTH = 640;
export const WAVE_HEIGHT = 280;
const SAMPLES = 160;

export interface WavePoint {
  x: number;
  y: number;
}

export interface WaveClock {
  /** Breath cycles elapsed. The fractional part is the position in the current breath. */
  cycle: number;
  /** Monotonic lateral phase, in radians. Integrated so a changing intensity cannot jump the surface. */
  travel: number;
}

export interface WavePalette {
  frontHi: string;
  frontMid: string;
  frontLo: string;
  backHi: string;
  backLo: string;
  midHi: string;
  midLo: string;
  foam: string;
}

export interface WaveFrame {
  back: WavePoint[];
  mid: WavePoint[];
  front: WavePoint[];
  surge: number;
  tension: number;
  palette: WavePalette;
  foamWidth: number;
  foamOpacity: number;
  foamDash: string;
  paths: {
    back: string;
    mid: string;
    front: string;
    foam: string;
  };
}

interface WaveLayer {
  scale: number;
  cycles: number;
  speed: number;
  phase: number;
  /** Breath lag in cycles. Negative means this layer leads the front. */
  lag: number;
  yOffset: number;
  edge: number;
}

const LAYERS: WaveLayer[] = [
  { scale: 0.64, cycles: 1.35, speed: 0.64, phase: 1.15, lag: -0.028, yOffset: -14, edge: 0.42 },
  { scale: 0.84, cycles: 2.2, speed: 0.94, phase: -0.48, lag: -0.012, yOffset: -6, edge: 0.7 },
  { scale: 1, cycles: 2.8, speed: 1.16, phase: 0.12, lag: 0, yOffset: 0, edge: 1 },
];

/** Water rests in the lower portion of the stage so the trough still reads as a sea, not an empty frame. */
const TROUGH_LINE = 214;

export function createWaveClock(): WaveClock {
  return { cycle: 0, travel: 0 };
}

export function severityOf(level: number): number {
  return Math.pow(clamp01(level / 10), 1.18);
}

/** Wall-clock length of one rise-and-fall at a fixed intensity. */
export function breathPeriodMs(level: number): number {
  return 10400 - severityOf(level) * 8600;
}

export function breathAtCycle(level: number, cycle: number): { surge: number; tension: number; rising: boolean } {
  const severity = severityOf(level);
  const riseShare = 0.42 - severity * 0.16;
  const u = frac(cycle);

  if (u < riseShare) {
    const t = u / riseShare;
    return {
      surge: Math.pow(t, 1.45 + severity * 0.55),
      tension: Math.pow(t, 0.8),
      rising: true,
    };
  }

  const t = (u - riseShare) / (1 - riseShare);
  return {
    surge: Math.pow(1 - t, 1.2),
    tension: Math.pow(1 - t, 2.5),
    rising: false,
  };
}

export function stepWaveClock(clock: WaveClock, deltaMs: number, level: number): WaveClock {
  const dt = Math.max(0, deltaMs);
  if (dt === 0) return clock;
  const period = breathPeriodMs(level);
  const mid = breathAtCycle(level, clock.cycle + dt / period / 2);
  const severity = severityOf(level);
  // High urge keeps moving; only the trough of that urge eases off. Low urge stays slow.
  const rate = (0.00028 + Math.pow(severity, 1.65) * 0.0035) * (0.38 + 0.62 * mid.tension);
  return {
    cycle: clock.cycle + dt / period,
    travel: clock.travel + dt * rate,
  };
}

export function waveFrame(level: number, clock: WaveClock): WaveFrame {
  const severity = severityOf(level);
  const center = breathAtCycle(level, clock.cycle);
  const back = layerPoints(LAYERS[0], level, severity, clock);
  const mid = layerPoints(LAYERS[1], level, severity, clock);
  const front = layerPoints(LAYERS[2], level, severity, clock);
  const tension = center.tension;
  const surge = center.surge;

  return {
    back,
    mid,
    front,
    surge,
    tension,
    palette: paletteFor(surge, tension),
    foamWidth: 1.7 + tension * 3.1,
    foamOpacity: 0.38 + tension * 0.58,
    foamDash: tension > 0.72 ? "none" : `${(13 - tension * 7).toFixed(1)} ${(11 - tension * 6).toFixed(1)}`,
    paths: {
      back: fillPath(back),
      mid: fillPath(mid),
      front: fillPath(front),
      foam: linePath(front),
    },
  };
}

export function surfaceStats(points: WavePoint[]): {
  meanY: number;
  minY: number;
  maxY: number;
  maxAbsSlope: number;
  crestCount: number;
} {
  let minY = Infinity;
  let maxY = -Infinity;
  let sum = 0;
  let maxAbsSlope = 0;
  for (let i = 0; i < points.length; i += 1) {
    const y = points[i].y;
    sum += y;
    if (y < minY) minY = y;
    if (y > maxY) maxY = y;
    if (i > 0) {
      const dx = points[i].x - points[i - 1].x || 1e-3;
      maxAbsSlope = Math.max(maxAbsSlope, Math.abs((y - points[i - 1].y) / dx));
    }
  }

  let crestCount = 0;
  for (let i = 1; i < points.length - 1; i += 1) {
    if (points[i].y > points[i - 1].y || points[i].y > points[i + 1].y) continue;
    let left = i;
    while (left > 0 && points[left - 1].y >= points[left].y) left -= 1;
    let right = i;
    while (right < points.length - 1 && points[right + 1].y >= points[right].y) right += 1;
    const base = Math.min(points[left].y, points[right].y);
    if (base - points[i].y >= 6) crestCount += 1;
  }

  return { meanY: sum / points.length, minY, maxY, maxAbsSlope, crestCount };
}

function layerPoints(layer: WaveLayer, level: number, severity: number, clock: WaveClock): WavePoint[] {
  const points: WavePoint[] = [];
  for (let i = 0; i <= SAMPLES; i += 1) {
    const position = i / SAMPLES;
    const x = position * WAVE_WIDTH;
    // The right side lags so a rise arrives as a surge instead of a flat elevator.
    const spatialLag = position * severity * 0.016;
    const breath = breathAtCycle(level, clock.cycle - layer.lag - spatialLag);
    const peakLine = 90 - severity * 20;
    const waterline = TROUGH_LINE - breath.surge * (TROUGH_LINE - peakLine) + layer.yOffset;
    // Intensity sets how worked-up the surface is. The crest tightens it further;
    // a deep trough is what lets a strong urge look soft again.
    const drive = severity * (0.34 + 0.66 * breath.tension);
    const cycles = layer.cycles * (1 + 1.35 * drive);
    const sharp = Math.pow(drive, 0.8) * layer.edge;
    const fullAmp = (15 + Math.pow(severity, 1.12) * 20) * layer.scale;
    const amp = fullAmp * (0.56 + 0.44 * breath.surge);
    const angle = position * Math.PI * 2 * cycles + clock.travel * layer.speed + layer.phase;
    const crown = Math.sin(position * Math.PI) * breath.surge * (3 + severity * 8) * layer.scale;
    const y = containY(waterline - crown - profile(angle, amp, sharp));
    points.push({ x, y });
  }
  return points;
}

/** Stokes-style profile: round at sharp=0, peaked and slightly leaned as sharp approaches 1. */
function profile(angle: number, amp: number, sharp: number): number {
  const fundamental = Math.sin(angle);
  const peak = -Math.cos(2 * angle);
  const lean = Math.sin(2 * angle + 0.6);
  const chop = Math.sin(3 * angle - 0.35);
  return amp * (fundamental + sharp * 0.48 * peak + sharp * 0.2 * lean + sharp * sharp * 0.06 * chop);
}

function paletteFor(surge: number, tension: number): WavePalette {
  const mood = clamp01(tension * 0.78 + surge * 0.22);
  return {
    frontHi: mixHex("#8ed4c6", "#f4fbff", mood),
    frontMid: mixHex("#6aa4ea", "#3d78d8", mood),
    frontLo: mixHex("#3c6eb4", "#17346f", mood),
    backHi: mixHex("#c5d6fb", "#e7f1ff", mood),
    backLo: mixHex("#6c98f4", "#355892", mood),
    midHi: mixHex("#b7e6df", "#d9fff6", mood),
    midLo: mixHex("#4d86c8", "#2a4f92", mood),
    foam: mixHex("#d7e8f8", "#ffffff", mood),
  };
}

function fillPath(points: WavePoint[]): string {
  return `M 0 ${WAVE_HEIGHT} L ${linePath(points).slice(2)} L ${WAVE_WIDTH} ${WAVE_HEIGHT} Z`;
}

function linePath(points: WavePoint[]): string {
  return `M ${points.map((point) => `${point.x.toFixed(1)} ${point.y.toFixed(1)}`).join(" L ")}`;
}

function containY(y: number): number {
  if (y < 2) return 2;
  if (y > WAVE_HEIGHT - 2) return WAVE_HEIGHT - 2;
  return y;
}

function frac(cycle: number): number {
  return ((cycle % 1) + 1) % 1;
}

function clamp01(value: number): number {
  return Math.min(1, Math.max(0, value));
}

function mixHex(from: string, to: string, t: number): string {
  const amount = clamp01(t);
  const [ar, ag, ab] = hexChannels(from);
  const [br, bg, bb] = hexChannels(to);
  return `#${channel(ar, br, amount)}${channel(ag, bg, amount)}${channel(ab, bb, amount)}`;
}

function hexChannels(hex: string): [number, number, number] {
  return [
    Number.parseInt(hex.slice(1, 3), 16),
    Number.parseInt(hex.slice(3, 5), 16),
    Number.parseInt(hex.slice(5, 7), 16),
  ];
}

function channel(from: number, to: number, t: number): string {
  return Math.round(from + (to - from) * t).toString(16).padStart(2, "0");
}
