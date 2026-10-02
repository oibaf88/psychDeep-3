export interface TrajectorySignal {
  signal_id: string;
  feature: string;
  band: string;
  change?: number | null;
  recent_mean?: number | null;
  baseline_mean?: number | null;
  uncertainty?: Record<string, unknown>;
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
    record_count?: number;
    minimum_records?: number;
  };
}

const PATIENT_FEATURES = new Set(["mood", "craving", "sleep_hours", "self_efficacy"]);

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

function formatMeasure(feature: string, value: number): string {
  const shown = value.toLocaleString("es-ES", { maximumFractionDigits: 1 });
  return feature === "sleep_hours" ? `${shown} h` : `${shown} de 10`;
}

export function calculatedChangeText(signal: TrajectorySignal): string {
  if (typeof signal.recent_mean === "number" && typeof signal.baseline_mean === "number") {
    const recentDays = countOf(signal.uncertainty, "recent_days") ?? 7;
    const baselineDays = countOf(signal.uncertainty, "baseline_days") ?? 21;
    return `En los últimos ${recentDays} días está en ${formatMeasure(signal.feature, signal.recent_mean)}. En los últimos ${baselineDays} días estaba en ${formatMeasure(signal.feature, signal.baseline_mean)}.`;
  }
  return `${featureLabel(signal.feature)} se compara con lo habitual en ti.`;
}

export function insufficientChangeNotice(signals: TrajectorySignal[]): string {
  const pending = latestByFeature(signals).filter(
    (signal) => PATIENT_FEATURES.has(signal.feature) && !signalWasCalculated(signal),
  );
  if (!pending.length) {
    return "Todavía no se ha calculado un cambio con los registros de este gráfico. Hacen falta al menos 5 días en los últimos 21. Esa falta de cálculo no significa que todo vaya bien.";
  }
  const counts = pending
    .map((signal) => countOf(signal.uncertainty, "baseline_n"))
    .filter((count): count is number => count != null);
  const records = counts.length ? Math.max(...counts) : null;
  const minimum = countOf(pending[0].uncertainty, "minimum_records") ?? 5;
  const countText = records == null ? "" : ` En los últimos 21 días hay ${records} registros y hacen falta al menos ${minimum}.`;
  return `Todavía no se ha calculado el cambio de ${joinSpanish(pending.map((signal) => featureLabel(signal.feature)))}.${countText} El gráfico muestra el registro; eso todavía no es una comparación. Esa falta de cálculo no significa que todo vaya bien.`;
}

export function baselineReady(snapshot: BaselineSnapshot | null): boolean {
  const row = snapshot?.baseline;
  if (!row || snapshot.status === "insufficient_data") return false;
  if (row.stability !== "eligible" && row.stability !== "partial") return false;
  return typeof row.data_coverage === "number" && row.data_coverage > 0;
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

export function baselineGapText(snapshot: BaselineSnapshot | null): string {
  const records = snapshot?.baseline?.record_count;
  const minimum = snapshot?.baseline?.minimum_records ?? 5;
  if (typeof records === "number") {
    return `En los últimos 21 días hay ${records} registros. Hacen falta al menos ${minimum} para compararlos con tu referencia. El gráfico muestra esos registros; todavía no hay un cálculo de cambio. Esa ausencia no se interpreta como normalidad.`;
  }
  return "Todavía no hay datos suficientes para describir cómo sueles estar. Mientras la referencia sea insuficiente, no se calcula un cambio y esa ausencia no se interpreta como normalidad.";
}

export function baselineStabilityLabel(stability: string): string {
  if (stability === "eligible") return "Cubre las áreas del registro";
  if (stability === "partial") return "Solo algunas áreas tienen registros suficientes";
  return patientBand(stability);
}
