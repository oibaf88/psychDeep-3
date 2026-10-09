import { describe, expect, it } from "vitest";
import {
  baselineCoverage,
  baselineHero,
  calculatedChangeText,
  featureEvidenceText,
  formatEvidenceMean,
  insufficientChangeNotice,
  patientBand,
  signalWasCalculated,
  type TrajectorySignal,
} from "../trendReading";

const insufficient = [
  { signal_id: "1", feature: "mood", band: "insufficient_data", change: null, algorithm_version: "canonical-structural-v1" },
  { signal_id: "2", feature: "craving", band: "insufficient_data", change: null, algorithm_version: "canonical-structural-v1" },
  { signal_id: "3", feature: "sleep_hours", band: "insufficient_data", change: null, algorithm_version: "canonical-structural-v1" },
  { signal_id: "4", feature: "self_efficacy", band: "insufficient_data", change: null, algorithm_version: "canonical-structural-v1" },
  { signal_id: "5", feature: "structural_composite", band: "insufficient_data", change: null, algorithm_version: "canonical-structural-v1" },
];

function availableEvidence(overrides?: Partial<NonNullable<TrajectorySignal["evidence"]>>): NonNullable<TrajectorySignal["evidence"]> {
  return {
    status: "available",
    axis: "mood",
    inverted: false,
    recent: {
      feature_value_id: "fv-1",
      mean: 6.4,
      n: 6,
      missing: false,
      window: { start: "2026-09-26", end: "2026-10-02" },
      quality_flags: [],
      feature_version: "v1",
      algorithm_version: "canonical-structural-v2",
    },
    reference: {
      baseline_version_id: "bv-1",
      mean: 5.1,
      std: 1.2,
      n: 12,
      eligible: true,
    },
    reproduced_from_rows: true,
    ...overrides,
  };
}

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

  it("formats available FeatureValue/Baseline evidence in plain Spanish", () => {
    const signal: TrajectorySignal = {
      signal_id: "mood-1",
      feature: "mood",
      band: "transition",
      change: 1.1,
      uncertainty: { recent_n: 6, baseline_n: 12 },
      evidence: availableEvidence(),
    };
    const text = featureEvidenceText(signal);
    expect(text).toContain("media fue 6.4");
    expect(text).toContain("6 registros");
    expect(text).toContain("referencia personal es 5.1");
    expect(text).toContain("12 registros");
    expect(text).toContain("coincide con esos registros");
    expect(text).not.toContain("canonical-structural");
    expect(text).not.toContain("feature_value");
    expect(text).not.toMatch(/sin riesgo|no hay riesgo/i);
    expect(formatEvidenceMean(null)).toBeNull();
    expect(formatEvidenceMean(0)).toBe("0");
  });

  it("uses explicit missingness language when evidence is insufficient", () => {
    const signal: TrajectorySignal = {
      signal_id: "sleep-1",
      feature: "sleep_hours",
      band: "insufficient_data",
      change: null,
      evidence: {
        status: "insufficient_data",
        axis: "sleep_hours",
        inverted: false,
        recent: {
          feature_value_id: "fv-sleep",
          mean: null,
          n: 0,
          missing: true,
          quality_flags: ["no_recent_observations"],
        },
        reference: null,
        reproduced_from_rows: null,
      },
    };
    const text = featureEvidenceText(signal);
    expect(text).toContain("Todavía no se puede explicar");
    expect(text).toContain("no significa que todo vaya bien");
    expect(text).toContain("faltan observaciones recientes");
    expect(text).not.toMatch(/sin riesgo|no hay riesgo/i);
    expect(text).not.toContain("canonical-structural");
  });

  it("skips composite evidence and notes a mismatched reproduction", () => {
    expect(
      featureEvidenceText({
        signal_id: "composite",
        feature: "structural_composite",
        band: "unstable",
        change: 1.2,
        evidence: null,
      }),
    ).toBeNull();

    const mismatched = featureEvidenceText({
      signal_id: "mood-2",
      feature: "mood",
      band: "transition",
      change: 0.8,
      evidence: availableEvidence({ reproduced_from_rows: false }),
    });
    expect(mismatched).toContain("ya no coincide exactamente");
    expect(mismatched).not.toMatch(/sin riesgo/i);
  });

  it("describes a completely missing evidence payload without inventing health", () => {
    const text = featureEvidenceText({
      signal_id: "craving-1",
      feature: "craving",
      band: "stable",
      change: 0.1,
    });
    expect(text).toContain("Todavía no hay evidencia");
    expect(text).toContain("no significa que todo vaya bien");
    expect(text).not.toMatch(/\b0\b.*salud|sin riesgo/i);
  });
});
