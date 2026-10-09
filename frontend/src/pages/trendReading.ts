export interface TrajectorySignal {
  signal_id: string;
  feature: string;
  band: string;
  change?: number | null;
  uncertainty?: Record<string, unknown>;
  contradictions?: unknown[] | null;
  window?: { start?: string; end?: string };
  algorithm_version?: string;
  evidence?: FeatureEvidence | null;
}

export interface FeatureEvidenceRecent {
  feature_value_id?: string;
  mean: number | null;
  n: number;
  missing: boolean;
  window?: { start?: string; end?: string };
  quality_flags?: string[];
  feature_version?: string;
  algorithm_version?: string;
}

export interface FeatureEvidenceReference {
  baseline_version_id?: string;
  mean: number | null;
  std?: number | null;
  n: number;
  eligible: boolean;
}

export interface FeatureEvidence {
  status: "available" | "insufficient_data" | string;
  axis?: string;
  inverted?: boolean;
  recent: FeatureEvidenceRecent | null;
  reference: FeatureEvidenceReference | null;
  reproduced_from_rows: boolean | null;
}

export interface BaselineSnapshot {
  status: string;
  baseline: null | {
    stability: string;
    data_coverage?: number | null;
    window?: { start: string; end: string };
    algorithm_version?: string;
  };
}

const FEATURE_LABELS: Record<string, string> = {
  mood: "Ánimo",
  craving: "Craving",
  sleep_hours: "Sueño",
  self_efficacy: "Autoeficacia",
  structural_composite: "El conjunto de tus registros",
};

const CALCULATED_BANDS: Record<string, string> = {
  stable: "Cerca de lo habitual en ti",
  transition: "Un poco distinto de lo habitual en ti",
  unstable: "Bastante distinto de lo habitual en ti",
};

const QUALITY_FLAG_LABELS: Record<string, string> = {
  no_recent_observations: "faltan observaciones recientes",
};

export function featureLabel(feature: string): string {
  return FEATURE_LABELS[feature] ?? feature.replace(/_/g, " ");
}

export function signalWasCalculated(signal: TrajectorySignal): boolean {
  return signal.band !== "insufficient_data" && signal.change != null && signal.band in CALCULATED_BANDS;
}

export function latestByFeature(signals: TrajectorySignal[]): TrajectorySignal[] {
  const seen = new Set<string>();
  const latest: TrajectorySignal[] = [];
  for (const signal of signals) {
    if (seen.has(signal.feature)) continue;
    seen.add(signal.feature);
    latest.push(signal);
  }
  return latest;
}

function countOf(uncertainty: Record<string, unknown> | undefined, key: string): number | null {
  const value = uncertainty?.[key];
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function joinSpanish(items: string[]): string {
  if (items.length <= 1) return items[0] ?? "";
  return `${items.slice(0, -1).join(", ")} y ${items[items.length - 1]}`;
}

/** Patient-facing number: never invent a health zero from a missing mean. */
export function formatEvidenceMean(value: number | null | undefined): string | null {
  if (value == null || !Number.isFinite(value)) return null;
  const rounded = Math.round(value * 10) / 10;
  return Number.isInteger(rounded) ? String(rounded) : rounded.toFixed(1);
}

function formatEvidenceDay(value?: string | null): string | null {
  if (!value) return null;
  const day = /^\d{4}-\d{2}-\d{2}/.exec(value)?.[0] ?? value;
  const parsed = new Date(/^\d{4}-\d{2}-\d{2}$/.test(day) ? `${day}T12:00:00` : day);
  if (Number.isNaN(parsed.getTime())) return day;
  return parsed.toLocaleDateString("es-ES", { day: "numeric", month: "short" });
}

function windowPhrase(window?: { start?: string; end?: string } | null): string {
  const start = formatEvidenceDay(window?.start);
  const end = formatEvidenceDay(window?.end);
  if (start && end) return ` (${start} – ${end})`;
  if (end) return ` (hasta ${end})`;
  if (start) return ` (desde ${start})`;
  return "";
}

function qualityMissingness(recent: FeatureEvidenceRecent | null | undefined): string {
  if (!recent) return "";
  const notes: string[] = [];
  if (recent.missing) notes.push("los registros recientes de esta área faltan o no se pudieron resumir");
  for (const flag of recent.quality_flags ?? []) {
    const label = QUALITY_FLAG_LABELS[flag] ?? null;
    if (label && !notes.some((note) => note.includes(label))) notes.push(label);
  }
  if (!notes.length) return "";
  return ` Atención: ${joinSpanish(notes)}. Esa falta no significa que todo vaya bien.`;
}

function reproductionPhrase(reproduced: boolean | null | undefined): string {
  if (reproduced === true) return " La comparación guardada coincide con esos registros.";
  if (reproduced === false) {
    return " La comparación guardada ya no coincide exactamente con esos registros; conviene no interpretarla sola.";
  }
  return "";
}

/**
 * Plain-Spanish evidence under a per-feature change card.
 * Composite has no single FeatureValue (`evidence: null`) — returns null.
 * Never presents missingness as zero, health or “sin riesgo”.
 */
export function featureEvidenceText(signal: TrajectorySignal): string | null {
  if (signal.feature === "structural_composite") return null;
  const evidence = signal.evidence;
  if (evidence == null) {
    return "Todavía no hay evidencia de los registros recientes o de tu referencia personal para explicar esta comparación. Esa falta no significa que todo vaya bien.";
  }

  if (evidence.status !== "available") {
    const recent = evidence.recent;
    const reference = evidence.reference;
    const parts: string[] = [];
    if (recent?.missing || recent == null) {
      parts.push("faltan datos recientes suficientes");
    } else if (recent.n != null) {
      parts.push(`solo hay ${recent.n} registro${recent.n === 1 ? "" : "s"} reciente${recent.n === 1 ? "" : "s"}`);
    }
    if (reference == null || !reference.eligible) {
      parts.push("tu referencia personal aún no es suficiente");
    }
    const detail = parts.length ? ` Ahora mismo ${joinSpanish(parts)}.` : "";
    return `Todavía no se puede explicar esta comparación con tus registros.${detail} Esa falta no significa que todo vaya bien ni que no haya cambio.${qualityMissingness(recent)}`;
  }

  const recentMean = formatEvidenceMean(evidence.recent?.mean);
  const referenceMean = formatEvidenceMean(evidence.reference?.mean);
  const recentN = evidence.recent?.n;
  const referenceN = evidence.reference?.n;
  if (recentMean == null || referenceMean == null || recentN == null || referenceN == null) {
    return `Todavía faltan datos para explicar esta comparación con tus registros. Esa falta no significa que todo vaya bien.${qualityMissingness(evidence.recent)}`;
  }

  const recentWindow = windowPhrase(evidence.recent?.window);
  return (
    `En este periodo${recentWindow} la media fue ${recentMean} (${recentN} registro${recentN === 1 ? "" : "s"}). ` +
    `Tu referencia personal es ${referenceMean} (${referenceN} registro${referenceN === 1 ? "" : "s"}).` +
    reproductionPhrase(evidence.reproduced_from_rows) +
    qualityMissingness(evidence.recent)
  );
}

export function patientBand(band: string): string {
  return CALCULATED_BANDS[band] ?? "Todavía no se puede calcular";
}

export function calculatedChangeText(
  signal: TrajectorySignal,
  options?: { includeRiskBoundary?: boolean },
): string {
  const recent = countOf(signal.uncertainty, "recent_n");
  const reference = countOf(signal.uncertainty, "baseline_n");
  const comparison =
    recent != null && reference != null
      ? ` Usa ${recent} registros de este periodo y ${reference} de tu referencia personal.`
      : "";
  const boundary = options?.includeRiskBoundary === false ? "" : " No es una alerta de riesgo.";
  return `${featureLabel(signal.feature)} se compara con lo que es habitual en ti.${comparison}${boundary}`;
}

export function insufficientChangeNotice(signals: TrajectorySignal[]): string {
  const pending = latestByFeature(signals).filter(
    (signal) => signal.feature !== "structural_composite" && !signalWasCalculated(signal),
  );
  const areas = pending.length ? ` Falta esa comparación en ${joinSpanish(pending.map((signal) => featureLabel(signal.feature)))}.` : "";
  return `Todavía no se ha calculado un cambio: no hay datos suficientes para comparar este periodo con tu propia referencia.${areas} Esa falta de cálculo no significa que todo vaya bien.`;
}

export function baselineReady(snapshot: BaselineSnapshot | null): boolean {
  const row = snapshot?.baseline;
  if (!row || snapshot.status === "insufficient_data" || row.stability === "insufficient_data") return false;
  return snapshot.status === "active" || snapshot.status === "provisional" || snapshot.status === "frozen";
}

export function baselineHero(snapshot: BaselineSnapshot | null): string {
  if (!baselineReady(snapshot)) return "Aún insuficiente";
  if (snapshot?.status === "provisional") return "Todavía provisional";
  if (snapshot?.baseline?.stability === "partial") return "Solo algunas áreas";
  return "Ya hay referencia";
}

export function baselineCoverage(snapshot: BaselineSnapshot | null): string {
  const coverage = snapshot?.baseline?.data_coverage;
  if (coverage == null) return "Cobertura no disponible";
  if (coverage <= 0) return "Todavía sin cobertura";
  return `${Math.round(coverage * 100)}% de las áreas con referencia`;
}

export function baselineStatusLabel(status: string): string {
  if (status === "active") return "Sirve como referencia";
  if (status === "provisional") return "Todavía provisional";
  if (status === "frozen") return "Conservada, sin recalcular";
  return "Aún insuficiente";
}

export function baselineStabilityLabel(stability: string): string {
  if (stability === "eligible") return "Cubre las áreas del registro";
  if (stability === "partial") return "Solo algunas áreas tienen registros suficientes";
  return patientBand(stability);
}
