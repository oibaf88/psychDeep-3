import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import LongitudinalChangePanel from "../../components/LongitudinalChangePanel";
import type { LongitudinalStateOut } from "../../api";
import {
  dashboardChangeDetail,
  dashboardChangeHeadline,
  formatChangeValue,
  readProfessionalChange,
} from "../professionalChange";

const calculated: LongitudinalStateOut = {
  baseline: {
    status: "provisional",
    baseline: {
      id: "base-1",
      stability: "partial",
      data_coverage: 0.5,
      algorithm_version: "canonical-structural-v1",
    },
  },
  changes: [
    {
      signal_id: "mood-1",
      feature: "mood",
      band: "unstable",
      change: 2.5,
      uncertainty: { baseline_n: 8, recent_n: 4 },
      algorithm_version: "canonical-structural-v1",
    },
    {
      signal_id: "sleep-1",
      feature: "sleep_hours",
      band: "insufficient_data",
      change: null,
      uncertainty: { reason: "insufficient_baseline_or_recent", baseline_n: 0, recent_n: 0 },
      algorithm_version: "canonical-structural-v1",
    },
    {
      signal_id: "composite-1",
      feature: "structural_composite",
      band: "transition",
      change: 1.1,
      algorithm_version: "canonical-structural-v1",
    },
  ],
  limits: ["La ausencia de una señal de cambio no demuestra ausencia de riesgo."],
};

describe("professional change reading", () => {
  it("keeps a calculated band distinct from an alert level and does not zero the gap", () => {
    expect(formatChangeValue(null)).toBe("Sin cálculo");
    expect(formatChangeValue(undefined)).toBe("Sin cálculo");
    expect(dashboardChangeHeadline(calculated)).toBe("Un poco distinto de su referencia personal");
    expect(dashboardChangeDetail(calculated)).toContain("no es una alerta");
    expect(dashboardChangeDetail(calculated)).toContain("hay áreas sin cálculo");
    expect(dashboardChangeDetail(calculated)).toContain("50% de las áreas con referencia");

    const reading = readProfessionalChange(calculated);
    const sleep = reading.rows.find((row) => row.feature === "sleep_hours");
    expect(sleep?.changeLabel).toBe("Sin cálculo");
    expect(sleep?.bandLabel).toBe("Datos insuficientes");
    expect(sleep?.missingNote).toContain("sin registros");
    expect(sleep?.missingNote).not.toContain("0");
    expect(reading.missingSentence).toContain("Sueño");
    expect(reading.missingSentence).toContain("no se guarda como cero");
    expect(reading.limit).toContain("no demuestra ausencia de riesgo");
    expect(reading.baselineLabel).toBe("Todavía provisional");
    expect(reading.coverageLabel).toBe("50% de las áreas con referencia");
  });

  it("says insufficient data when the canonical read has no rows", () => {
    const empty: LongitudinalStateOut = {
      baseline: { status: "insufficient_data", baseline: null },
      changes: [],
      limits: ["La ausencia de una señal de cambio no demuestra ausencia de riesgo."],
    };
    expect(dashboardChangeHeadline(empty)).toBe("Datos insuficientes");
    expect(dashboardChangeDetail(empty)).toContain("Cobertura no disponible");
    expect(readProfessionalChange(empty).coverageLabel).toBe("Cobertura no disponible");
    const measuredZero: LongitudinalStateOut = {
      baseline: {
        status: "provisional",
        baseline: { id: "base-0", stability: "insufficient_data", data_coverage: 0 },
      },
      changes: [],
    };
    expect(readProfessionalChange(measuredZero).coverageLabel).toBe("Todavía sin cobertura");
    expect(readProfessionalChange(measuredZero).coverageLabel).not.toMatch(/0%/);
    expect(readProfessionalChange(null).limit).toContain("ausencia de riesgo");
  });

  it("renders the change panel without using the alert level", () => {
    render(<LongitudinalChangePanel longitudinal={calculated} />);
    expect(screen.getByRole("heading", { name: "Cambio respecto a su línea de base" })).toBeInTheDocument();
    expect(screen.getByText("Bastante distinto de su referencia personal")).toBeInTheDocument();
    expect(screen.getByText("Cambio: 2.50")).toBeInTheDocument();
    expect(screen.getByText("Sin cálculo")).toBeInTheDocument();
    expect(screen.getByText(/no demuestra ausencia de riesgo/)).toBeInTheDocument();
    expect(screen.queryByText(/N3|nivel de alerta 3|alerta N/)).not.toBeInTheDocument();
    expect(screen.queryByText("0.00")).not.toBeInTheDocument();
  });
});
