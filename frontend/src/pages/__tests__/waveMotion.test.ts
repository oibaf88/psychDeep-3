import { describe, expect, it } from "vitest";
import {
  WAVE_HEIGHT,
  breathAtCycle,
  breathPeriodMs,
  createWaveClock,
  stepWaveClock,
  surfaceStats,
  waveFrame,
  type WaveClock,
  type WaveFrame,
} from "../../waveMotion";

function frameAt(level: number, cycle: number, travel = 1.2): WaveFrame {
  return waveFrame(level, { cycle, travel });
}

function samplesOverBreath(level: number): WaveFrame[] {
  const frames: WaveFrame[] = [];
  for (let i = 0; i <= 48; i += 1) frames.push(frameAt(level, i / 48));
  return frames;
}

function span(values: number[]): number {
  return Math.max(...values) - Math.min(...values);
}

describe("waveMotion", () => {
  it("lifts and drops the surface a long way at a fixed intensity", () => {
    for (const level of [2, 5, 9]) {
      const frames = samplesOverBreath(level);
      const tops = frames.map((frame) => surfaceStats(frame.front).minY);
      const means = frames.map((frame) => surfaceStats(frame.front).meanY);
      expect(span(tops)).toBeGreaterThan(WAVE_HEIGHT * 0.4);
      expect(span(means)).toBeGreaterThan(WAVE_HEIGHT * 0.35);
    }
  });

  it("makes a higher intensity faster, steeper and busier", () => {
    expect(breathPeriodMs(10)).toBeLessThan(breathPeriodMs(2) * 0.35);
    expect(breathPeriodMs(1)).toBeGreaterThan(8_000);
    expect(breathPeriodMs(10)).toBeLessThan(2_500);

    const calmCrest = samplesOverBreath(2).reduce((best, frame) => (frame.surge > best.surge ? frame : best));
    const stormCrest = samplesOverBreath(10).reduce((best, frame) => (frame.surge > best.surge ? frame : best));
    const calm = surfaceStats(calmCrest.front);
    const storm = surfaceStats(stormCrest.front);
    expect(storm.maxAbsSlope).toBeGreaterThan(calm.maxAbsSlope * 3);
    expect(storm.crestCount).toBeGreaterThan(calm.crestCount);
  });

  it("is sharper and more crowded at the peak than in the trough", () => {
    const frames = samplesOverBreath(8);
    const crest = frames.reduce((best, frame) => (frame.surge > best.surge ? frame : best));
    const trough = frames.reduce((best, frame) => (frame.surge < best.surge ? frame : best));
    const crestStats = surfaceStats(crest.front);
    const troughStats = surfaceStats(trough.front);
    expect(crest.tension).toBeGreaterThan(0.85);
    expect(trough.tension).toBeLessThan(0.2);
    expect(crestStats.maxAbsSlope).toBeGreaterThan(troughStats.maxAbsSlope * 2.5);
    expect(crestStats.crestCount).toBeGreaterThan(troughStats.crestCount);
  });

  it("spends longer falling than rising, and lets the texture loosen while the water is still descending", () => {
    let rise = 0;
    let fall = 0;
    for (let i = 0; i < 100; i += 1) {
      if (breathAtCycle(9, i / 100).rising) rise += 1;
      else fall += 1;
    }
    expect(fall).toBeGreaterThan(rise * 1.8);

    const severityBreath = breathAtCycle(8, 0.72);
    expect(severityBreath.rising).toBe(false);
    expect(severityBreath.surge).toBeGreaterThan(0.25);
    expect(severityBreath.tension).toBeLessThan(0.25);
  });

  it("keeps three distinct layers inside the stage", () => {
    const frame = frameAt(6, 0.22, 2.4);
    const gap = Math.max(...frame.front.map((point, index) => Math.abs(point.y - frame.back[index].y)));
    expect(gap).toBeGreaterThan(12);
    expect(frame.paths.front).not.toBe(frame.paths.back);
    expect(frame.paths.front.endsWith("Z")).toBe(true);
    expect(frame.paths.foam.startsWith("M")).toBe(true);
    expect(frame.paths.foam.includes("Z")).toBe(false);

    for (const level of [0, 5, 10]) {
      for (let step = 0; step <= 16; step += 1) {
        const sample = frameAt(level, step / 16, step * 0.8);
        for (const point of [...sample.front, ...sample.mid, ...sample.back]) {
          expect(point.y).toBeGreaterThan(8);
          expect(point.y).toBeLessThan(WAVE_HEIGHT - 2);
        }
      }
    }
  });

  it("advances one breath per period and never rewinds the travel", () => {
    const level = 6;
    const clock = stepWaveClock(createWaveClock(), breathPeriodMs(level), level);
    expect(clock.cycle).toBeCloseTo(1, 5);

    let cursor: WaveClock = createWaveClock();
    let previous = cursor.travel;
    for (let step = 0; step < 30; step += 1) {
      cursor = stepWaveClock(cursor, 40, 9);
      expect(cursor.travel).toBeGreaterThanOrEqual(previous);
      previous = cursor.travel;
    }
  });
});
