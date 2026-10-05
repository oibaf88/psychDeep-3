import { BAND_LABELS } from "./api";

/** Risk-engine check-in similarity. Not a ChangeSignal band and not an alert level. */
export function riskEngineBandText(band: string | null | undefined): string {
  if (!band || !band.trim()) return "Banda del motor no calculada";
  return `Banda del motor: ${BAND_LABELS[band] || band}`;
}

/** A missing structural score stays absent. A real 0 is only shown when the engine stored 0. */
export function riskEngineScoreText(score: number | null | undefined): string {
  if (typeof score !== "number" || !Number.isFinite(score)) return "Sin score del motor";
  return score.toFixed(2);
}
