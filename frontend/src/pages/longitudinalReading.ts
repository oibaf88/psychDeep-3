import {
  baselineCoverage,
  baselineReady,
  baselineStabilityLabel,
  baselineStatusLabel,
  calculatedChangeText,
  featureLabel,
  insufficientChangeNotice,
  patientBand,
  signalWasCalculated,
  type BaselineSnapshot,
  type TrajectorySignal,
} from "./trendReading";

export interface PatientStateResponse {
  latest?: Record<string, unknown>;
  missing?: string[];
  safety?: {
    alert_level?: number | null;
    assessment_id?: string | null;
    model_version?: string | null;
    correlation_id?: string | null;
  };
  longitudinal?: {
    baseline?: BaselineSnapshot | null;
    changes?: TrajectorySignal[];
  } | null;
  limits?: string[];
}

export interface ChangeFeatureLine {
  signalId: string;
  label: string;
  bandLabel: string;
  detail: string;
}

export interface LongitudinalFraming {
  baselineStatus: string;
  referenceQuality: string;
  coverage: string;
  headline: string;
  explanation: string;
  featureLines: ChangeFeatureLine[];
  pendingNotice: string | null;
  missingNotice: string | null;
  limits: string[];
}

const ABSENCE_LIMIT = "La ausencia de una señal no demuestra ausencia de riesgo.";

const COMPARISON_BOUNDARY =
  "Esto compara tus registros recientes con lo habitual en ti. No es una alerta de riesgo.";

function joinSpanish(items: string[]): string {
  if (items.length <= 1) return items[0] ?? "";
  if (items.length === 2) return `${items[0]} y ${items[1]}`;
  return `${items.slice(0, -1).join(", ")} y ${items[items.length - 1]}`;
}

function uniqueText(values: Array<string | null | undefined> | undefined): string[] {
  const seen = new Set<string>();
  const result: string[] = [];
  for (const value of values ?? []) {
    const text = value?.trim();
    if (!text || seen.has(text)) continue;
    seen.add(text);
    result.push(text);
  }
  return result;
}

function contradictionNote(signal: TrajectorySignal): string {
  if (!Array.isArray(signal.contradictions) || signal.contradictions.length === 0) return "";
  return " Hay contexto contradictorio registrado; la señal de cambio se conserva.";
}

function missingNotice(missing: string[] | undefined): string | null {
  const labels = uniqueText(missing).map((feature) => featureLabel(feature));
  if (!labels.length) return null;
  return `Faltan observaciones recientes de ${joinSpanish(labels)}. Esa ausencia no se interpreta como cero ni como ausencia de cambio.`;
}

/**
 * Patient-facing change-versus-baseline copy from GET /api/v1/state.
 * Reads `longitudinal` only. Safety alert levels are intentionally ignored
 * so a ChangeSignal band is never presented as a RiskAssessment.
 */
export function longitudinalFraming(state: PatientStateResponse | null | undefined): LongitudinalFraming {
  const baseline = state?.longitudinal?.baseline ?? null;
  const changes = state?.longitudinal?.changes ?? [];
  const ready = baselineReady(baseline);
  const comparable = changes.filter((change) => change.feature !== "structural_composite");
  const calculated = comparable.filter(signalWasCalculated);
  const pending = comparable.filter((change) => !signalWasCalculated(change));
  const whole = changes.find((change) => change.feature === "structural_composite" && signalWasCalculated(change));
  const nothingCalculated = calculated.length === 0 && !whole;

  let headline = "Todavía no hay una comparación con tu línea de base";
  if (calculated.length && !whole) headline = "Hay comparación solo en algunas áreas";
  if (ready && whole) headline = patientBand(whole.band);

  const explanation = ready && whole ? calculatedChangeText(whole) : COMPARISON_BOUNDARY;

  return {
    baselineStatus: ready ? baselineStatusLabel(baseline?.status ?? "") : "Aún insuficiente",
    referenceQuality: ready
      ? baselineStabilityLabel(baseline?.baseline?.stability ?? "")
      : "Sin referencia suficiente",
    coverage: baselineCoverage(baseline),
    headline,
    explanation,
    featureLines: calculated.map((change) => ({
      signalId: change.signal_id,
      label: featureLabel(change.feature),
      bandLabel: patientBand(change.band),
      detail: `${calculatedChangeText(change, { includeRiskBoundary: false })}${contradictionNote(change)}`,
    })),
    pendingNotice: pending.length || nothingCalculated ? insufficientChangeNotice(changes) : null,
    missingNotice: missingNotice(state?.missing),
    limits: uniqueText([...(state?.limits ?? []), ABSENCE_LIMIT]),
  };
}
