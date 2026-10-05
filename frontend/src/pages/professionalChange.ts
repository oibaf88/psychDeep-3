import type { LongitudinalChangeOut, LongitudinalStateOut } from "../api";
import {
  baselineCoverage,
  baselineStabilityLabel,
  baselineStatusLabel,
  type BaselineSnapshot,
} from "./trendReading";

function toSnapshot(state: LongitudinalStateOut | null | undefined): BaselineSnapshot | null {
  const baseline = state?.baseline;
  if (!baseline) return null;
  return {
    status: baseline.status,
    baseline: baseline.baseline
      ? {
          stability: baseline.baseline.stability ?? "insufficient_data",
          data_coverage: baseline.baseline.data_coverage,
        }
      : null,
  };
}

const FEATURE_LABELS: Record<string, string> = {
  mood: "Ánimo",
  craving: "Craving",
  sleep_hours: "Sueño",
  self_efficacy: "Autoeficacia",
  structural_composite: "Conjunto de registros",
};

const CALCULATED_BANDS: Record<string, string> = {
  stable: "Cerca de su referencia personal",
  transition: "Un poco distinto de su referencia personal",
  unstable: "Bastante distinto de su referencia personal",
};

const FEATURE_ORDER = ["mood", "craving", "sleep_hours", "self_efficacy", "structural_composite"];

export const CHANGE_IS_NOT_RISK = "La ausencia de una señal de cambio no demuestra ausencia de riesgo.";

export function featureLabel(feature: string): string {
  return FEATURE_LABELS[feature] ?? feature.replace(/_/g, " ");
}

export function changeWasCalculated(signal: LongitudinalChangeOut): boolean {
  return signal.band in CALCULATED_BANDS && typeof signal.change === "number" && Number.isFinite(signal.change);
}

export function professionalBandLabel(band: string): string {
  return CALCULATED_BANDS[band] ?? "Datos insuficientes";
}

export function formatChangeValue(change: number | null | undefined): string {
  if (typeof change !== "number" || !Number.isFinite(change)) return "Sin cálculo";
  return `Distancia respecto a su referencia: ${change.toFixed(2)}. No es un nivel de alerta.`;
}

function countLabel(value: unknown): string {
  if (typeof value !== "number" || !Number.isFinite(value)) return "no disponible";
  if (value <= 0) return "sin registros";
  return String(Math.round(value));
}

export function missingnessNote(signal: LongitudinalChangeOut): string | null {
  if (changeWasCalculated(signal)) return null;
  const baselineN = countLabel(signal.uncertainty?.baseline_n);
  const recentN = countLabel(signal.uncertainty?.recent_n);
  return `Sin cálculo: referencia ${baselineN}, registros recientes ${recentN}. No se interpreta como cero.`;
}

function orderedChanges(state: LongitudinalStateOut | null | undefined): LongitudinalChangeOut[] {
  const changes = state?.changes ?? [];
  return [...changes].sort((a, b) => {
    const ai = FEATURE_ORDER.indexOf(a.feature);
    const bi = FEATURE_ORDER.indexOf(b.feature);
    return (ai === -1 ? FEATURE_ORDER.length : ai) - (bi === -1 ? FEATURE_ORDER.length : bi);
  });
}

export function dashboardChangeHeadline(state: LongitudinalStateOut | null | undefined): string {
  if (!state) return "Sin lectura clínica";
  const composite = state.changes.find((row) => row.feature === "structural_composite");
  if (composite && changeWasCalculated(composite)) return professionalBandLabel(composite.band);
  const calculated = state.changes.filter(changeWasCalculated);
  if (calculated.length > 0) return "Solo algunas áreas";
  return "Datos insuficientes";
}

export function dashboardChangeDetail(state: LongitudinalStateOut | null | undefined): string {
  if (!state) return "Esta fila no incluye la trayectoria canónica.";
  const coverage = baselineCoverage(toSnapshot(state));
  const pending = state.changes.some((row) => row.feature !== "structural_composite" && !changeWasCalculated(row));
  const gap = pending ? " · hay áreas sin cálculo" : "";
  return `${coverage}${gap} · no es una alerta`;
}

export interface ProfessionalChangeRow {
  feature: string;
  label: string;
  bandLabel: string;
  changeLabel: string;
  missingNote: string | null;
  contradictionNote: string | null;
  calculated: boolean;
}

export interface ProfessionalChangeReading {
  intro: string;
  baselineLabel: string;
  stabilityLabel: string;
  coverageLabel: string;
  rows: ProfessionalChangeRow[];
  missingSentence: string | null;
  limit: string;
}

export function readProfessionalChange(state: LongitudinalStateOut | null | undefined): ProfessionalChangeReading {
  const rows = orderedChanges(state).map((signal) => {
    const calculated = changeWasCalculated(signal);
    return {
      feature: signal.feature,
      label: featureLabel(signal.feature),
      bandLabel: calculated ? professionalBandLabel(signal.band) : "Datos insuficientes",
      changeLabel: calculated ? formatChangeValue(signal.change) : "Sin cálculo",
      missingNote: missingnessNote(signal),
      contradictionNote:
        Array.isArray(signal.contradictions) && signal.contradictions.length > 0
          ? "Hay contexto contradictorio registrado. La señal de cambio se conserva y no se convierte en un nivel de alerta."
          : null,
      calculated,
    };
  });
  const missing = rows.filter((row) => row.feature !== "structural_composite" && !row.calculated);
  const missingSentence = missing.length
    ? `Sin cálculo en ${joinSpanish(missing.map((row) => row.label))}. Esa falta no se guarda como cero y no indica ausencia de riesgo.`
    : null;
  const limit = state?.limits?.find((item) => item.trim()) ?? CHANGE_IS_NOT_RISK;
  const snapshot = toSnapshot(state);
  return {
    intro: "Comparación con su referencia personal. Es independiente del nivel de alerta y del motor de riesgo.",
    baselineLabel: baselineStatusLabel(snapshot?.status ?? "insufficient_data"),
    stabilityLabel: snapshot?.baseline?.stability
      ? baselineStabilityLabel(snapshot.baseline.stability)
      : "Todavía no se puede calcular",
    coverageLabel: baselineCoverage(snapshot),
    rows,
    missingSentence,
    limit,
  };
}

function joinSpanish(items: string[]): string {
  if (items.length <= 1) return items[0] ?? "";
  return `${items.slice(0, -1).join(", ")} y ${items[items.length - 1]}`;
}
