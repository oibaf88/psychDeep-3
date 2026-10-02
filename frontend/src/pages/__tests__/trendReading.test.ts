import { describe, expect, it } from "vitest";
import {
  baselineCoverage,
  baselineHero,
  calculatedChangeText,
  insufficientChangeNotice,
  patientBand,
  signalWasCalculated,
} from "../trendReading";

const insufficient = [
  { signal_id: "1", feature: "mood", band: "insufficient_data", change: null, algorithm_version: "canonical-structural-v1" },
  { signal_id: "2", feature: "craving", band: "insufficient_data", change: null, algorithm_version: "canonical-structural-v1" },
  { signal_id: "3", feature: "sleep_hours", band: "insufficient_data", change: null, algorithm_version: "canonical-structural-v1" },
  { signal_id: "4", feature: "self_efficacy", band: "insufficient_data", change: null, algorithm_version: "canonical-structural-v1" },
  { signal_id: "5", feature: "structural_composite", band: "insufficient_data", change: null, algorithm_version: "canonical-structural-v1" },
];

describe("patient trajectory reading", () => {
  it("does not call an insufficient result a calculated signal", () => {
    const notice = insufficientChangeNotice(insufficient);
    expect(notice).toContain("no hay datos suficientes");
    expect(notice).not.toMatch(/señal calculada/i);
    expect(notice).not.toContain("canonical-structural");
    expect(notice).not.toContain("MOOD");
    expect(notice).not.toContain("SLEEP_HOURS");
    expect(notice.match(/Ánimo/g)).toHaveLength(1);
    expect(insufficient.filter(signalWasCalculated)).toHaveLength(0);
  });

  it("states a calculated comparison without the algorithm name", () => {
    const signal = {
      signal_id: "9",
      feature: "mood",
      band: "transition",
      change: 1.4,
      uncertainty: { recent_n: 6, baseline_n: 12 },
      algorithm_version: "canonical-structural-v1",
    };
    expect(signalWasCalculated(signal)).toBe(true);
    expect(patientBand(signal.band)).toBe("Un poco distinto de lo habitual en ti");
    const text = calculatedChangeText(signal);
    expect(text).toContain("6 registros de este periodo");
    expect(text).toContain("12 de tu referencia personal");
    expect(text).not.toContain("canonical-structural");
    expect(text).not.toMatch(/señal calculada/i);
  });

  it("keeps an empty reference out of technical status codes", () => {
    const snapshot = {
      status: "provisional",
      baseline: { stability: "insufficient_data", data_coverage: 0, window: { start: "2026-09-11", end: "2026-10-02" }, algorithm_version: "canonical-structural-v1" },
    };
    expect(baselineHero(snapshot)).toBe("Aún insuficiente");
    expect(baselineCoverage(snapshot)).toBe("Todavía sin cobertura");
  });
});
