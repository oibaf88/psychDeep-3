import { describe, expect, it } from "vitest";
import { longitudinalFraming, type PatientStateResponse } from "../longitudinalReading";

const windowRange = { start: "2026-09-01", end: "2026-10-01" };

function signal(
  feature: string,
  band: string,
  change: number | null,
  extra: Partial<PatientStateResponse["longitudinal"]> = {},
) {
  return {
    signal_id: feature,
    feature,
    band,
    change,
    uncertainty: change == null ? { reason: "insufficient_baseline_or_recent", baseline_n: 1, recent_n: 0 } : { recent_n: 6, baseline_n: 12 },
    contradictions: [] as unknown[],
    window: windowRange,
    ...extra,
  };
}

describe("longitudinalFraming", () => {
  it("reads change bands as a personal comparison and ignores the safety alert level", () => {
    const state: PatientStateResponse = {
      missing: [],
      safety: { alert_level: 4, assessment_id: "assessment-should-not-render" },
      longitudinal: {
        baseline: {
          status: "active",
          baseline: { stability: "eligible", data_coverage: 1, window: windowRange },
        },
        changes: [
          signal("mood", "transition", 1.2),
          signal("craving", "stable", 0.2),
          signal("sleep_hours", "stable", -0.1),
          signal("self_efficacy", "unstable", 2.4),
          signal("structural_composite", "unstable", 1.1),
        ],
      },
      limits: ["La ausencia de una señal no demuestra ausencia de riesgo."],
    };

    const framing = longitudinalFraming(state);
    const rendered = JSON.stringify(framing);

    expect(framing.headline).toBe("Bastante distinto de lo habitual en ti");
    expect(framing.baselineStatus).toBe("Sirve como referencia");
    expect(framing.coverage).toBe("100% de las áreas con referencia");
    expect(framing.explanation).toContain("No es una alerta de riesgo.");
    expect(framing.featureLines.map((line) => line.label)).toEqual(["Ánimo", "Craving", "Sueño", "Autoeficacia"]);
    expect(framing.featureLines.find((line) => line.label === "Ánimo")?.bandLabel).toBe(
      "Un poco distinto de lo habitual en ti",
    );
    expect(rendered).not.toContain("assessment-should-not-render");
    expect(rendered).not.toContain("unstable");
    expect(rendered).not.toContain("Nivel 4");
    expect(rendered).not.toMatch(/nivel de alerta\s*\d/i);
  });

  it("keeps insufficient data and missing observations explicit", () => {
    const state: PatientStateResponse = {
      missing: ["sleep_hours", "mood"],
      safety: { alert_level: null },
      longitudinal: {
        baseline: {
          status: "provisional",
          baseline: { stability: "insufficient_data", data_coverage: 0, window: windowRange },
        },
        changes: [
          signal("mood", "insufficient_data", null),
          signal("craving", "insufficient_data", null),
          signal("sleep_hours", "insufficient_data", null),
          signal("self_efficacy", "insufficient_data", null),
          signal("structural_composite", "insufficient_data", null),
        ],
      },
    };

    const framing = longitudinalFraming(state);
    const rendered = JSON.stringify(framing);

    expect(framing.headline).toBe("Todavía no hay una comparación con tu línea de base");
    expect(framing.baselineStatus).toBe("Aún insuficiente");
    expect(framing.coverage).toBe("Todavía sin cobertura");
    expect(framing.referenceQuality).toBe("Sin referencia suficiente");
    expect(framing.pendingNotice).toContain("no hay datos suficientes");
    expect(framing.pendingNotice).toContain("no significa que todo vaya bien");
    expect(framing.missingNotice).toContain("Sueño");
    expect(framing.missingNotice).toContain("Ánimo");
    expect(framing.missingNotice).toContain("no se interpreta como cero");
    expect(framing.limits).toContain("La ausencia de una señal no demuestra ausencia de riesgo.");
    expect(rendered).not.toContain("insufficient_data");
    expect(rendered).not.toMatch(/sin riesgo|no hay riesgo|0%/i);
    expect(framing.featureLines).toHaveLength(0);
  });

  it("preserves a contradictory change instead of dropping it", () => {
    const mood = signal("mood", "transition", 1.4);
    mood.contradictions = [{ kind: "context", note: "raw-contradiction-payload" }];
    const framing = longitudinalFraming({
      longitudinal: {
        baseline: {
          status: "provisional",
          baseline: { stability: "partial", data_coverage: 0.5, window: windowRange },
        },
        changes: [mood],
      },
    });

    expect(framing.headline).toBe("Hay comparación solo en algunas áreas");
    expect(framing.baselineStatus).toBe("Todavía provisional");
    expect(framing.referenceQuality).toBe("Solo algunas áreas tienen registros suficientes");
    expect(framing.featureLines[0]?.detail).toContain("la señal de cambio se conserva");
    expect(framing.featureLines[0]?.detail).not.toContain("raw-contradiction-payload");
  });
});
