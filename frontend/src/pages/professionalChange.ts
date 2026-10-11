/**
 * Roster/copilot one-liners. Kept as a thin adapter so every professional
 * surface uses the same reading as the dossier (see longitudinalModel.ts).
 */
import type { LongitudinalStateOut } from "../api";
import { CHANGE_IS_NOT_RISK, rosterDetail, rosterHeadline } from "./longitudinalModel";

export { CHANGE_IS_NOT_RISK };

export function dashboardChangeHeadline(state: LongitudinalStateOut | null | undefined): string {
  return rosterHeadline(state);
}

export function dashboardChangeDetail(state: LongitudinalStateOut | null | undefined): string {
  return rosterDetail(state);
}
