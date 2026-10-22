/**
 * Record Hoy suggested-action feedback on the canonical InterventionEvent path.
 *
 * Does not touch RiskAssessment, alert levels or clinical thresholds.
 * Failures are swallowed so a network error never blocks navigation or "No ahora".
 */
import { api } from "../api";
import type { HoyActionDriver, HoyActionId } from "./hoySuggestedAction";

export type FeedbackState = "accepted" | "rejected" | "postponed" | "completed";

export type PendingUsefulness = {
  actionId: HoyActionId;
  driver: HoyActionDriver;
  title: string;
  /** ChangeSignal that triggered the accepted action; absent/null when none did. */
  changeSignalId?: string | null;
  recordedAt: string;
};

const PENDING_KEY = "psychdeep.hoy.pendingUsefulness";

export async function recordHoyActionFeedback(input: {
  actionId: HoyActionId;
  state: FeedbackState;
  driver: HoyActionDriver;
  usefulness?: 1 | 2 | 3 | 4 | 5;
  changeSignalId?: string | null;
}): Promise<boolean> {
  try {
    await api.post("/api/v1/feedback", {
      action_id: input.actionId,
      state: input.state,
      usefulness: input.usefulness ?? null,
      reason: input.driver,
      change_signal_id: input.changeSignalId ?? null,
    });
    return true;
  } catch {
    return false;
  }
}

export function stashPendingUsefulness(pending: Omit<PendingUsefulness, "recordedAt">): void {
  try {
    const payload: PendingUsefulness = { ...pending, recordedAt: new Date().toISOString() };
    sessionStorage.setItem(PENDING_KEY, JSON.stringify(payload));
  } catch {
    /* private mode / quota — usefulness prompt simply will not appear */
  }
}

export function readPendingUsefulness(): PendingUsefulness | null {
  try {
    const raw = sessionStorage.getItem(PENDING_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as PendingUsefulness;
    if (
      !parsed ||
      typeof parsed.actionId !== "string" ||
      typeof parsed.driver !== "string" ||
      typeof parsed.title !== "string" ||
      (parsed.changeSignalId != null && typeof parsed.changeSignalId !== "string")
    ) {
      return null;
    }
    return parsed;
  } catch {
    return null;
  }
}

export function clearPendingUsefulness(): void {
  try {
    sessionStorage.removeItem(PENDING_KEY);
  } catch {
    /* ignore */
  }
}

/** Map the three plain-language usefulness answers to the 1–5 API scale. */
export function usefulnessFromChoice(choice: "helped" | "somewhat" | "not_really"): 1 | 3 | 5 {
  if (choice === "helped") return 5;
  if (choice === "somewhat") return 3;
  return 1;
}
