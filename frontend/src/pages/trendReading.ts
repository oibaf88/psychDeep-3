export interface TrajectorySignal {
  signal_id: string;
  feature: string;
  band: string;
  change?: number | null;
  uncertainty?: Record<string, unknown>;
  contradictions?: unknown[] | null;
  window?: { start?: string; end?: string };
  algorithm_version?: string;
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
