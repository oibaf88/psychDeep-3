import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { LongitudinalStateOut } from "../../api";
import { ApiError, api } from "../../api";
import BaselineFreezeControl, { freezeErrorMessage, supervisedFreezeRecord } from "../BaselineFreezeControl";

vi.mock("../../api", async () => {
  const actual = await vi.importActual<typeof import("../../api")>("../../api");
  return { ...actual, api: { get: vi.fn(), post: vi.fn() } };
});

const refWindow = { start: "2026-09-01", end: "2026-09-28" };

const activeBaseline: LongitudinalStateOut["baseline"] = {
  status: "active",
  baseline: {
    id: "b-active",
    stability: "eligible",
    data_coverage: 1,
    window: refWindow,
    algorithm_version: "canonical-structural-v3",
    exclusions: [{ kind: "recent_comparison_window" }],
  },
};

const frozenBaseline: LongitudinalStateOut["baseline"] = {
  status: "frozen",
  baseline: {
    id: "b-frozen",
    stability: "eligible",
    data_coverage: 1,
    window: refWindow,
    algorithm_version: "canonical-structural-v3",
    exclusions: [
      { kind: "recent_comparison_window" },
      {
        kind: "supervised_freeze",
        frozen_at: "2026-10-20T09:30:00+00:00",
        frozen_by: "therapist-1",
        frozen_by_role: "therapist",
        note: "Periodo de ingreso hospitalario",
        source_baseline_version_id: "b-active",
      },
    ],
  },
};

const insufficientBaseline: LongitudinalStateOut["baseline"] = { status: "insufficient_data", baseline: null };

function noteBox() {
  return screen.getByLabelText(/Nota \(obligatoria\)/);
}

describe("BaselineFreezeControl", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("shows the current state and requires a note before freezing", () => {
    render(<BaselineFreezeControl patientId="p1" baseline={activeBaseline} canAct />);
    expect(screen.getByTestId("baseline-freeze-state")).toHaveTextContent("Se recalcula con cada registro");
    expect(screen.getByText(/no modifica el nivel de alerta, el motor de riesgo ni sus umbrales/)).toBeInTheDocument();
    const submit = screen.getByRole("button", { name: "Conservar referencia" });
    expect(submit).toBeDisabled();
    fireEvent.change(noteBox(), { target: { value: "  a " } });
    expect(submit).toBeDisabled();
    fireEvent.change(noteBox(), { target: { value: "Ingreso" } });
    expect(submit).toBeEnabled();
    expect(screen.queryByRole("button", { name: /Liberar/ })).not.toBeInTheDocument();
  });

  it("posts the trimmed note to the freeze endpoint and reloads", async () => {
    vi.mocked(api.post).mockResolvedValue({ status: "frozen", baseline: null });
    const onChanged = vi.fn();
    render(<BaselineFreezeControl patientId="p1" baseline={activeBaseline} canAct onChanged={onChanged} />);
    fireEvent.change(noteBox(), { target: { value: "  Periodo de ingreso hospitalario  " } });
    fireEvent.click(screen.getByRole("button", { name: "Conservar referencia" }));
    await waitFor(() => expect(onChanged).toHaveBeenCalledTimes(1));
    expect(api.post).toHaveBeenCalledWith("/api/v1/professional/patients/p1/baseline/freeze", {
      reason: "Periodo de ingreso hospitalario",
    });
    expect(screen.getByRole("status")).toHaveTextContent("Referencia conservada");
    expect(noteBox()).toHaveValue("");
  });

  it("shows the frozen record and releases only after confirmation", async () => {
    vi.mocked(api.post).mockResolvedValue({ status: "active", baseline: null });
    const onChanged = vi.fn();
    render(<BaselineFreezeControl patientId="p1" baseline={frozenBaseline} canAct onChanged={onChanged} />);
    expect(screen.getByTestId("baseline-freeze-state")).toHaveTextContent("Conservada, sin recalcular");
    expect(screen.getByText("Periodo de ingreso hospitalario")).toBeInTheDocument();
    expect(screen.getByText("terapeuta asignado")).toBeInTheDocument();
    expect(screen.queryByLabelText(/Nota \(obligatoria\)/)).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Liberar referencia" }));
    expect(api.post).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button", { name: "Cancelar" }));
    expect(screen.queryByRole("button", { name: "Confirmar liberación" })).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Liberar referencia" }));
    fireEvent.click(screen.getByRole("button", { name: "Confirmar liberación" }));
    await waitFor(() => expect(onChanged).toHaveBeenCalledTimes(1));
    expect(api.post).toHaveBeenCalledWith("/api/v1/professional/patients/p1/baseline/release");
    expect(screen.getByRole("status")).toHaveTextContent("Referencia liberada");
  });

  it("a 403 explains who may act and does not reload", async () => {
    vi.mocked(api.post).mockRejectedValue(new ApiError("Se requiere asignación activa y consentimiento de compartición", 403));
    const onChanged = vi.fn();
    render(<BaselineFreezeControl patientId="p1" baseline={activeBaseline} canAct onChanged={onChanged} />);
    fireEvent.change(noteBox(), { target: { value: "Motivo clínico" } });
    fireEvent.click(screen.getByRole("button", { name: "Conservar referencia" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(/solo el terapeuta asignado con consentimiento/);
    expect(onChanged).not.toHaveBeenCalled();
    expect(noteBox()).toHaveValue("Motivo clínico");
  });

  it("a 422 explains the note rule; a 409 shows the conflict and asks to reload", async () => {
    vi.mocked(api.post).mockRejectedValueOnce(new ApiError("reason: String should have at least 3 characters", 422));
    render(<BaselineFreezeControl patientId="p1" baseline={activeBaseline} canAct />);
    fireEvent.change(noteBox(), { target: { value: "Motivo" } });
    fireEvent.click(screen.getByRole("button", { name: "Conservar referencia" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("La nota es obligatoria y debe tener entre 3 y 1000 caracteres.");

    vi.mocked(api.post).mockRejectedValueOnce(new ApiError("La referencia personal ya está conservada", 409));
    fireEvent.click(screen.getByRole("button", { name: "Conservar referencia" }));
    await waitFor(() =>
      expect(screen.getByRole("alert")).toHaveTextContent(
        "La referencia personal ya está conservada. Recarga la ficha para ver el estado actual.",
      ),
    );
  });

  it("is read-only for non-therapists but still shows the frozen state", () => {
    render(<BaselineFreezeControl patientId="p1" baseline={frozenBaseline} canAct={false} />);
    expect(screen.getByTestId("baseline-freeze-state")).toHaveTextContent("Conservada, sin recalcular");
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
    expect(screen.getByText(/Solo el terapeuta asignado con consentimiento de compartición vigente/)).toBeInTheDocument();
  });

  it("offers no freeze when there is no sufficient reference", () => {
    render(<BaselineFreezeControl patientId="p1" baseline={insufficientBaseline} canAct />);
    expect(screen.getByTestId("baseline-freeze-state")).toHaveTextContent("Sin referencia suficiente");
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
    expect(screen.getByText(/No hay una referencia personal con datos suficientes/)).toBeInTheDocument();
  });

  it("helpers: freeze record and error mapping", () => {
    expect(supervisedFreezeRecord(activeBaseline)).toBeNull();
    expect(supervisedFreezeRecord(frozenBaseline)?.note).toBe("Periodo de ingreso hospitalario");
    expect(supervisedFreezeRecord({ status: "frozen", baseline: { id: "x" } })).toEqual({});
    expect(freezeErrorMessage(new ApiError("No se pudo conectar", 0))).toBe("No se pudo conectar");
  });
});
