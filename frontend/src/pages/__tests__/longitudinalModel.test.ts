import { describe, expect, it } from "vitest";
import { deriveSummary, readComparison, rosterDetail, rosterHeadline } from "../longitudinalModel";
import {
  calculatedLongitudinal,
  insufficientLongitudinal,
  migratedLongitudinal,
  noRecentLongitudinal,
  partialLongitudinal,
} from "./longitudinalFixtures";

function allText(reading: ReturnType<typeof readComparison>): string {
  return JSON.stringify(reading);
}

describe("readComparison", () => {
  it("shows values, direction and counts behind a calculated comparison (bug 1)", () => {
    const reading = readComparison(calculatedLongitudinal, "patient");
    expect(reading.headline).toBe("Bastante distinto de lo habitual en ti");
    const mood = reading.rows.find((row) => row.feature === "mood")!;
    expect(mood.valueLine).toBe("3,5/10 de media en el periodo reciente frente a 6,4/10 en tu referencia.");
    expect(mood.directionLine).toBe("Ánimo más bajo que lo habitual (-2,9 puntos).");
    expect(mood.countsLine).toContain("6 registros recientes · 21 en la referencia");
    const sleep = reading.rows.find((row) => row.feature === "sleep_hours")!;
    expect(sleep.valueLine).toContain("5 h de media");
  });

  it("presents craving on the declared scale, never inverted", () => {
    const craving = readComparison(calculatedLongitudinal, "professional").rows.find((r) => r.feature === "craving")!;
    expect(craving.recentValue).toBe(6.67);
    expect(craving.referenceValue).toBe(2.62);
    expect(craving.directionLine).toBe("Más deseo de consumo que lo habitual (+4,1 puntos).");
    expect(craving.zText).toBe("+4,1");
  });

  it("never says there is a reference while saying there is no data (bug 3)", () => {
    for (const state of [migratedLongitudinal, insufficientLongitudinal, noRecentLongitudinal]) {
      const text = allText(readComparison(state, "patient"));
      expect(text).not.toMatch(/Sirve como referencia|Ya hay referencia|Cubre las áreas/);
    }
    const migrated = readComparison(migratedLongitudinal, "patient");
    expect(migrated.status).toBe("not_computed");
    expect(migrated.headline).toBe("Todavía no se ha calculado tu comparación");
    expect(migrated.facts.map((f) => f.value)).toEqual(["Comparación sin calcular", "0 de 4", "Aún no"]);
  });

  it("names the real reason when the reference exists but recent check-ins are missing", () => {
    const reading = readComparison(noRecentLongitudinal, "patient");
    expect(reading.headline).toBe("Tu referencia está lista, pero faltan registros recientes");
    expect(reading.rows[0].missingLine).toBe("Ánimo: no hay registros en los últimos 7 días (la referencia tiene 21).");
    expect(reading.staleNotice).toMatch(/puede no describir cómo estás ahora/);
  });

  it("explains an insufficient reference with counts and the minimum", () => {
    const reading = readComparison(insufficientLongitudinal, "patient");
    expect(reading.explanation).toContain("al menos 5 registros por área");
    expect(reading.rows[0].missingLine).toBe("Ánimo: tu referencia tiene 0 de los 5 registros mínimos (4 registros recientes).");
    expect(allText(reading)).not.toMatch(/sin riesgo|no hay riesgo|insufficient_data"?\s*[,}]/i);
  });

  it("partial comparison lists what is missing instead of 'no se ha calculado un cambio'", () => {
    const reading = readComparison(partialLongitudinal, "patient");
    expect(reading.headline).toBe("Comparación en 3 de 4 áreas");
    expect(reading.pendingNotice).toContain("Falta la comparación en Sueño");
    expect(allText(reading)).not.toContain("Todavía no se ha calculado un cambio");
  });

  it("derives the same status when an older payload has no summary", () => {
    const { summary: _drop, ...legacyPayload } = calculatedLongitudinal;
    expect(deriveSummary(legacyPayload).status).toBe("calculated");
    const { summary: _drop2, ...partialPayload } = partialLongitudinal;
    expect(deriveSummary(partialPayload).status).toBe("partial");
  });

  it("roster lines come from the same reading", () => {
    expect(rosterHeadline(calculatedLongitudinal)).toBe("Bastante distinto de su referencia personal");
    expect(rosterDetail(calculatedLongitudinal)).toMatch(/^4 de 4 áreas · .* · no es una alerta$/);
    expect(rosterHeadline(migratedLongitudinal)).toBe("Comparación aún no calculada");
    expect(rosterHeadline(null)).toBe("Sin lectura longitudinal");
  });
});
