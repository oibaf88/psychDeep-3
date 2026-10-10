import type { LongitudinalChangeOut, LongitudinalStateOut } from "../../api";

const recentWindow = { start: "2026-10-03T12:00:00Z", end: "2026-10-10T12:00:00Z" };
const referenceWindow = { start: "2026-09-12T12:00:00Z", end: "2026-10-03T12:00:00Z" };

type Display = { recent: number; reference: number; z: number; direction: "higher" | "lower" | "similar"; unit?: string };

export function signal(feature: string, band: string, change: number | null, display?: Display, counts = { recent_n: 6, baseline_n: 21 }): LongitudinalChangeOut {
  return {
    signal_id: `${feature}-id`,
    feature,
    band,
    change,
    window: recentWindow,
    uncertainty: change == null ? { reason: "insufficient_baseline_or_recent", ...counts } : counts,
    contradictions: [],
    algorithm_version: "canonical-structural-v2",
    evidence:
      feature === "structural_composite"
        ? null
        : {
            status: display ? "available" : "insufficient_data",
            recent: { mean: display?.recent ?? null, n: counts.recent_n, missing: counts.recent_n === 0 },
            reference: display ? { mean: display.reference, n: counts.baseline_n, eligible: true } : null,
            reproduced_from_rows: display ? true : null,
            display: display
              ? {
                  unit: display.unit ?? (feature === "sleep_hours" ? "h" : "0-10"),
                  recent_value: display.recent,
                  reference_value: display.reference,
                  difference: Math.round((display.recent - display.reference) * 100) / 100,
                  direction: display.direction,
                  z: display.z,
                }
              : { unit: feature === "sleep_hours" ? "h" : "0-10", recent_value: null, reference_value: null, difference: null, direction: null, z: null },
          },
  };
}

const canonicalBaseline = {
  status: "active",
  baseline: { id: "b1", stability: "eligible", data_coverage: 1, window: referenceWindow, algorithm_version: "canonical-structural-v2" },
};

export const calculatedLongitudinal: LongitudinalStateOut = {
  baseline: canonicalBaseline,
  changes: [
    signal("mood", "unstable", -2.88, { recent: 3.5, reference: 6.38, z: -2.88, direction: "lower" }),
    signal("craving", "unstable", -4.05, { recent: 6.67, reference: 2.62, z: 4.05, direction: "higher" }),
    signal("sleep_hours", "unstable", -3.76, { recent: 4.95, reference: 6.86, z: -3.76, direction: "lower" }),
    signal("self_efficacy", "unstable", -2.93, { recent: 3.5, reference: 6.43, z: -2.93, direction: "lower" }),
    signal("structural_composite", "unstable", 3.4),
  ],
  summary: {
    status: "calculated",
    calculated_features: ["mood", "craving", "sleep_hours", "self_efficacy"],
    pending_features: [],
    computed_at: recentWindow.end,
    recent_window: recentWindow,
    reference_window: referenceWindow,
    algorithm_version: "canonical-structural-v2",
    is_stale: false,
    minimum_reference_n: 5,
  },
};

export const insufficientLongitudinal: LongitudinalStateOut = {
  baseline: { status: "provisional", baseline: { id: "b2", stability: "insufficient_data", data_coverage: 0, window: referenceWindow, algorithm_version: "canonical-structural-v2" } },
  changes: ["mood", "craving", "sleep_hours", "self_efficacy", "structural_composite"].map((f) =>
    signal(f, "insufficient_data", null, undefined, { recent_n: 4, baseline_n: 0 }),
  ),
  summary: {
    status: "insufficient_reference",
    calculated_features: [],
    pending_features: ["mood", "craving", "sleep_hours", "self_efficacy"].map((feature) => ({
      feature,
      reason: "reference" as const,
      baseline_n: 0,
      recent_n: 4,
      minimum_reference_n: 5,
    })),
    computed_at: recentWindow.end,
    recent_window: recentWindow,
    reference_window: referenceWindow,
    algorithm_version: "canonical-structural-v2",
    is_stale: false,
    minimum_reference_n: 5,
  },
};

/** A patient migrated from the legacy engine who has not checked in since. */
export const migratedLongitudinal: LongitudinalStateOut = {
  baseline: { status: "insufficient_data", baseline: null },
  changes: [],
  summary: {
    status: "not_computed",
    calculated_features: [],
    pending_features: [],
    computed_at: null,
    recent_window: { start: null, end: null },
    reference_window: { start: null, end: null },
    algorithm_version: null,
    is_stale: false,
    minimum_reference_n: 5,
  },
};

export const noRecentLongitudinal: LongitudinalStateOut = {
  ...calculatedLongitudinal,
  changes: ["mood", "craving", "sleep_hours", "self_efficacy", "structural_composite"].map((f) =>
    signal(f, "insufficient_data", null, undefined, { recent_n: 0, baseline_n: 21 }),
  ),
  summary: {
    ...calculatedLongitudinal.summary!,
    status: "no_recent_data",
    calculated_features: [],
    pending_features: ["mood", "craving", "sleep_hours", "self_efficacy"].map((feature) => ({
      feature,
      reason: "recent" as const,
      baseline_n: 21,
      recent_n: 0,
      minimum_reference_n: 5,
    })),
    is_stale: true,
  },
};

export const partialLongitudinal: LongitudinalStateOut = {
  ...calculatedLongitudinal,
  changes: [
    calculatedLongitudinal.changes[0],
    calculatedLongitudinal.changes[1],
    signal("sleep_hours", "insufficient_data", null, undefined, { recent_n: 0, baseline_n: 21 }),
    calculatedLongitudinal.changes[3],
    signal("structural_composite", "insufficient_data", null),
  ],
  summary: {
    ...calculatedLongitudinal.summary!,
    status: "partial",
    calculated_features: ["mood", "craving", "self_efficacy"],
    pending_features: [{ feature: "sleep_hours", reason: "recent", baseline_n: 21, recent_n: 0, minimum_reference_n: 5 }],
  },
};
