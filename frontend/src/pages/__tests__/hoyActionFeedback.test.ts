import { beforeEach, describe, expect, it, vi } from "vitest";
import { api } from "../../api";
import {
  clearPendingUsefulness,
  readPendingUsefulness,
  recordHoyActionFeedback,
  stashPendingUsefulness,
  usefulnessFromChoice,
} from "../hoyActionFeedback";

vi.mock("../../api", async () => {
  const actual = await vi.importActual<typeof import("../../api")>("../../api");
  return {
    ...actual,
    api: {
      get: vi.fn(),
      post: vi.fn(),
    },
  };
});

describe("hoyActionFeedback", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    sessionStorage.clear();
  });

  it("maps plain-language usefulness to the 1–5 API scale", () => {
    expect(usefulnessFromChoice("helped")).toBe(5);
    expect(usefulnessFromChoice("somewhat")).toBe(3);
    expect(usefulnessFromChoice("not_really")).toBe(1);
  });

  it("posts accepted feedback with action_id and driver reason", async () => {
    vi.mocked(api.post).mockResolvedValue({ id: "evt-1", state: "accepted", usefulness: null });
    const ok = await recordHoyActionFeedback({
      actionId: "hoy.suggest.regular_wave",
      state: "accepted",
      driver: "longitudinal_adverse",
    });
    expect(ok).toBe(true);
    expect(api.post).toHaveBeenCalledWith("/api/v1/feedback", {
      action_id: "hoy.suggest.regular_wave",
      state: "accepted",
      usefulness: null,
      reason: "longitudinal_adverse",
      change_signal_id: null,
    });
  });

  it("sends the triggering ChangeSignal id when the suggestion had one", async () => {
    vi.mocked(api.post).mockResolvedValue({ id: "evt-2", state: "completed", usefulness: 3 });
    await recordHoyActionFeedback({
      actionId: "hoy.suggest.regular_wave",
      state: "completed",
      driver: "longitudinal_adverse",
      usefulness: 3,
      changeSignalId: "craving-id",
    });
    expect(api.post).toHaveBeenCalledWith("/api/v1/feedback", {
      action_id: "hoy.suggest.regular_wave",
      state: "completed",
      usefulness: 3,
      reason: "longitudinal_adverse",
      change_signal_id: "craving-id",
    });
  });

  it("keeps the triggering ChangeSignal id across the usefulness round-trip", () => {
    stashPendingUsefulness({
      actionId: "hoy.suggest.regular_wave",
      driver: "longitudinal_adverse",
      title: "Regular una ola",
      changeSignalId: "mood-id",
    });
    expect(readPendingUsefulness()?.changeSignalId).toBe("mood-id");
  });

  it("returns false without throwing when the feedback API fails", async () => {
    vi.mocked(api.post).mockRejectedValue(new Error("offline"));
    await expect(
      recordHoyActionFeedback({
        actionId: "hoy.suggest.trends_explain",
        state: "postponed",
        driver: "calculated_explain",
      }),
    ).resolves.toBe(false);
  });

  it("stashes and clears pending usefulness in sessionStorage", () => {
    expect(readPendingUsefulness()).toBeNull();
    stashPendingUsefulness({
      actionId: "hoy.suggest.register_observe",
      driver: "insufficient_observe",
      title: "Registrar y observar",
    });
    const pending = readPendingUsefulness();
    expect(pending?.actionId).toBe("hoy.suggest.register_observe");
    expect(pending?.title).toBe("Registrar y observar");
    clearPendingUsefulness();
    expect(readPendingUsefulness()).toBeNull();
  });
});
