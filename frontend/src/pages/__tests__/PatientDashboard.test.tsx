import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter } from "react-router-dom";
import PatientDashboard from "../PatientDashboard";
import { api } from "../../api";
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

import {
  calculatedLongitudinal,
  insufficientLongitudinal,
  migratedLongitudinal,
  stableLongitudinal,
} from "./longitudinalFixtures";

type PatientStateResponse = Record<string, unknown>;

const calculatedState: PatientStateResponse = {
  missing: [],
  safety: { alert_level: 4, assessment_id: "assessment-should-not-render" },
  longitudinal: calculatedLongitudinal,
  limits: ["La ausencia de una señal no demuestra ausencia de riesgo."],
};

const insufficientState: PatientStateResponse = {
  missing: ["sleep_hours", "mood"],
  safety: { alert_level: null, assessment_id: null },
  longitudinal: insufficientLongitudinal,
};

const migratedState: PatientStateResponse = {
  missing: [],
  safety: { alert_level: 1, assessment_id: "a" },
  longitudinal: migratedLongitudinal,
};

const stableState: PatientStateResponse = {
  missing: [],
  safety: { alert_level: 2, assessment_id: "must-not-drive-action" },
  longitudinal: stableLongitudinal,
  limits: ["La ausencia de una señal no demuestra ausencia de riesgo."],
};

function mockGets(state: PatientStateResponse) {
  vi.mocked(api.get).mockImplementation(async (path: string) => {
    if (path.startsWith("/api/v1/state")) return state;
    if (path.startsWith("/api/v1/timeline")) return { points: [] };
    if (path.startsWith("/api/v1/assignments")) return [];
    throw new Error(`unexpected ${path}`);
  });
}

function renderHoy() {
  return render(
    <MemoryRouter>
      <PatientDashboard />
    </MemoryRouter>,
  );
}

describe("PatientDashboard longitudinal change", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    sessionStorage.clear();
  });

  it("renders change versus the personal baseline without using the safety alert level", async () => {
    mockGets(calculatedState);
    renderHoy();

    const region = await screen.findByRole("region", { name: "Cambio respecto a tu línea de base" });
    expect(region).toHaveTextContent("Bastante distinto de lo habitual en ti");
    expect(region).toHaveTextContent("Ánimo más bajo que lo habitual (-2,9 puntos).");
    expect(region).toHaveTextContent("3,5/10 de media en el periodo reciente frente a 6,4/10 en tu referencia.");
    expect(region).toHaveTextContent("Más deseo de consumo que lo habitual");
    expect(region).toHaveTextContent("La ausencia de una señal de cambio no demuestra ausencia de riesgo.");
    expect(region).not.toHaveTextContent("Nivel 4");
    expect(region).not.toHaveTextContent("assessment-should-not-render");
    expect(region).not.toHaveTextContent("unstable");
    expect(region.className).not.toMatch(/alert-level|level-pill/);
    const summary = screen.getByRole("region", { name: "Resumen del cambio respecto a tu línea de base" });
    expect(summary).toHaveTextContent("Bastante distinto de lo habitual en ti");
    expect(summary).toHaveTextContent("Comparación calculada");
    expect(summary).toHaveTextContent("4 de 4");
    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent("Bastante distinto de lo habitual en ti");
    expect(screen.getByRole("button", { name: "Ocultar sugerencia por ahora" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Ir a Regular" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Ver Tendencias" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Abrir Tendencias" })).not.toBeInTheDocument();
    expect(screen.getByRole("region", { name: "Siguiente paso" })).not.toHaveTextContent(/sin riesgo|todo va bien/i);
    const checkin = screen.getByRole("heading", { name: "Check-in de hoy" });
    const detail = screen.getByRole("heading", { name: "Respecto a lo habitual en ti" });
    expect(checkin.compareDocumentPosition(detail) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(screen.queryByText("Nivel 4")).not.toBeInTheDocument();
  });

  it("states insufficient data and missingness without turning them into zero or no risk", async () => {
    mockGets(insufficientState);
    renderHoy();

    const region = await screen.findByRole("region", { name: "Cambio respecto a tu línea de base" });
    expect(region).toHaveTextContent("Aún no hay registros suficientes para tu referencia personal");
    expect(region).toHaveTextContent("Ánimo: tu referencia tiene 0 de los 5 registros mínimos (4 registros recientes).");
    expect(region).toHaveTextContent("eso no significa que todo vaya bien");
    expect(region).toHaveTextContent("La ausencia de una señal de cambio no demuestra ausencia de riesgo.");
    expect(region).not.toHaveTextContent(/sin riesgo|no hay riesgo|0%/i);
    expect(region).not.toHaveTextContent("insufficient_data");
    expect(within(region).queryByText("0")).not.toBeInTheDocument();
    const next = screen.getByRole("region", { name: "Siguiente paso" });
    expect(within(next).getByRole("button", { name: "Ver Tendencias" })).toBeInTheDocument();
    expect(next).toHaveTextContent("Registrar y observar");
    expect(next).not.toHaveTextContent(/sin riesgo|todo va bien|todo está bien/i);
    expect(within(next).queryByRole("button", { name: "Ir a Regular" })).not.toBeInTheDocument();
  });

  it("keeps No ahora and refreshes the comparison after a check-in", async () => {
    let phase: "before" | "after" = "before";
    vi.mocked(api.get).mockImplementation(async (path: string) => {
      if (path.startsWith("/api/v1/state")) return phase === "before" ? insufficientState : calculatedState;
      if (path.startsWith("/api/v1/timeline")) return { points: [] };
      if (path.startsWith("/api/v1/assignments")) return [];
      throw new Error(`unexpected ${path}`);
    });
    vi.mocked(api.post).mockImplementation(async (path: string) => {
      if (path.startsWith("/api/v1/feedback")) return { id: "evt", state: "postponed" };
      phase = "after";
      return {};
    });

    const user = userEvent.setup();
    renderHoy();

    expect(await screen.findByRole("button", { name: "Ocultar sugerencia por ahora" })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Ocultar sugerencia por ahora" }));
    expect(screen.getByRole("heading", { name: "Puedes dejarlo aquí" })).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Mostrar una opción" }));
    await user.click(screen.getByRole("button", { name: "Guardar check-in" }));

    expect(await screen.findByText("Check-in registrado.")).toBeInTheDocument();
    await waitFor(() => {
      expect(screen.getByRole("region", { name: "Cambio respecto a tu línea de base" })).toHaveTextContent(
        "Bastante distinto de lo habitual en ti",
      );
    });
    const region = screen.getByRole("region", { name: "Cambio respecto a tu línea de base" });
    expect(region).not.toHaveTextContent("Aún no hay registros suficientes");
    expect(region).not.toHaveTextContent("Nivel 4");
  });

  it("a migrated patient never sees 'reference ready' next to 'no data' (bug 3)", async () => {
    mockGets(migratedState);
    renderHoy();
    const summary = await screen.findByRole("region", { name: "Resumen del cambio respecto a tu línea de base" });
    await waitFor(() => expect(summary).toHaveTextContent("Todavía no se ha calculado tu comparación"));
    expect(document.body).not.toHaveTextContent(/Sirve como referencia|Cubre las áreas|Ya hay referencia/);
    expect(summary).toHaveTextContent("Comparación sin calcular");
  });

  it("with a stable-only longitudinal reading suggests Tendencias, not Regular", async () => {
    mockGets(stableState);
    renderHoy();

    const next = await screen.findByRole("region", { name: "Siguiente paso" });
    expect(within(next).getByRole("button", { name: "Ver Tendencias" })).toBeInTheDocument();
    expect(next).toHaveTextContent(/explicación del cambio|Tendencias/i);
    expect(within(next).queryByRole("button", { name: "Ir a Regular" })).not.toBeInTheDocument();
    expect(next).not.toHaveTextContent(/Nivel 2|must-not-drive-action|sin riesgo/i);
  });

  it("insufficient longitudinal keeps No ahora and a soft Tendencias option", async () => {
    mockGets(insufficientState);
    const user = userEvent.setup();
    renderHoy();

    expect(await screen.findByRole("button", { name: "Ver Tendencias" })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Ocultar sugerencia por ahora" }));
    expect(screen.getByRole("heading", { name: "Puedes dejarlo aquí" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Ir a Regular" })).not.toBeInTheDocument();
  });
  it("records postponed feedback when No ahora is pressed", async () => {
    mockGets(insufficientState);
    vi.mocked(api.post).mockResolvedValue({ id: "evt-postponed", state: "postponed" });
    const user = userEvent.setup();
    renderHoy();

    expect(await screen.findByRole("button", { name: "Ocultar sugerencia por ahora" })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Ocultar sugerencia por ahora" }));

    await waitFor(() => {
      expect(api.post).toHaveBeenCalledWith("/api/v1/feedback", {
        action_id: "hoy.suggest.register_observe",
        state: "postponed",
        usefulness: null,
        reason: "insufficient_observe",
      });
    });
    expect(screen.getByRole("heading", { name: "Puedes dejarlo aquí" })).toBeInTheDocument();
  });

  it("records accepted feedback and shows usefulness when returning with a pending stash", async () => {
    sessionStorage.setItem(
      "psychdeep.hoy.pendingUsefulness",
      JSON.stringify({
        actionId: "hoy.suggest.regular_wave",
        driver: "longitudinal_adverse",
        title: "Regular una ola",
        recordedAt: "2026-10-14T08:00:00.000Z",
      }),
    );
    mockGets(calculatedState);
    vi.mocked(api.post).mockResolvedValue({ id: "evt-done", state: "completed", usefulness: 5 });
    const user = userEvent.setup();
    renderHoy();

    const useful = await screen.findByRole("region", { name: "Utilidad de la opción anterior" });
    expect(useful).toHaveTextContent("¿Te resultó útil «Regular una ola»?");
    expect(useful).toHaveTextContent(/No cambia tu comparación ni un nivel de alerta/i);
    expect(useful).not.toHaveTextContent(/sin riesgo|Nivel 4/i);

    await user.click(screen.getByRole("button", { name: "Sí, ayudó" }));

    await waitFor(() => {
      expect(api.post).toHaveBeenCalledWith("/api/v1/feedback", {
        action_id: "hoy.suggest.regular_wave",
        state: "completed",
        usefulness: 5,
        reason: "longitudinal_adverse",
      });
    });
    expect(sessionStorage.getItem("psychdeep.hoy.pendingUsefulness")).toBeNull();
    expect(await screen.findByText(/Queda registrado si te resultó útil/i)).toBeInTheDocument();
  });
});
