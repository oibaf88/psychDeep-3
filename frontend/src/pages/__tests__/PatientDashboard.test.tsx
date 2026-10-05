import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter } from "react-router-dom";
import PatientDashboard from "../PatientDashboard";
import { api } from "../../api";
import type { PatientStateResponse } from "../longitudinalReading";

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

const windowRange = { start: "2026-09-01", end: "2026-10-01" };

function signal(feature: string, band: string, change: number | null) {
  return {
    signal_id: `${feature}-id`,
    feature,
    band,
    change,
    uncertainty:
      change == null
        ? { reason: "insufficient_baseline_or_recent", baseline_n: 0, recent_n: 0 }
        : { recent_n: 6, baseline_n: 12 },
    contradictions: [],
    window: windowRange,
  };
}

const calculatedState: PatientStateResponse = {
  missing: [],
  safety: { alert_level: 4, assessment_id: "assessment-should-not-render" },
  longitudinal: {
    baseline: {
      status: "active",
      baseline: { stability: "eligible", data_coverage: 1, window: windowRange },
    },
    changes: [
      signal("mood", "transition", 1.2),
      signal("craving", "stable", 0.2),
      signal("sleep_hours", "stable", -0.1),
      signal("self_efficacy", "unstable", 2.4),
      signal("structural_composite", "unstable", 1.1),
    ],
  },
  limits: ["La ausencia de una señal no demuestra ausencia de riesgo."],
};

const insufficientState: PatientStateResponse = {
  missing: ["sleep_hours", "mood"],
  safety: { alert_level: null, assessment_id: null },
  longitudinal: {
    baseline: {
      status: "insufficient_data",
      baseline: null,
    },
    changes: [
      signal("mood", "insufficient_data", null),
      signal("craving", "insufficient_data", null),
      signal("sleep_hours", "insufficient_data", null),
      signal("self_efficacy", "insufficient_data", null),
      signal("structural_composite", "insufficient_data", null),
    ],
  },
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
  });

  it("renders change versus the personal baseline without using the safety alert level", async () => {
    mockGets(calculatedState);
    renderHoy();

    const region = await screen.findByRole("region", { name: "Cambio respecto a tu línea de base" });
    expect(region).toHaveTextContent("Bastante distinto de lo habitual en ti");
    expect(region).toHaveTextContent("Un poco distinto de lo habitual en ti");
    expect(region).toHaveTextContent("Ánimo");
    expect(region).toHaveTextContent("Sirve como referencia");
    expect(region).toHaveTextContent("100% de las áreas con referencia");
    expect(region).toHaveTextContent("No es una alerta de riesgo.");
    expect(region).toHaveTextContent("No es un nivel de alerta");
    expect(region).toHaveTextContent("La ausencia de una señal no demuestra ausencia de riesgo.");
    expect(region).not.toHaveTextContent("Nivel 4");
    expect(region).not.toHaveTextContent("assessment-should-not-render");
    expect(region).not.toHaveTextContent("unstable");
    expect(region.className).not.toMatch(/alert-level|level-pill/);
    expect(screen.getByRole("region", { name: "Resumen del cambio respecto a tu línea de base" })).toHaveTextContent(
      "Bastante distinto de lo habitual en ti",
    );
    expect(screen.getByRole("button", { name: "Ocultar sugerencia por ahora" })).toBeInTheDocument();
    expect(screen.queryByText("Nivel 4")).not.toBeInTheDocument();
  });

  it("states insufficient data and missingness without turning them into zero or no risk", async () => {
    mockGets(insufficientState);
    renderHoy();

    const region = await screen.findByRole("region", { name: "Cambio respecto a tu línea de base" });
    expect(region).toHaveTextContent("Todavía no hay una comparación con tu línea de base");
    expect(region).toHaveTextContent("no hay datos suficientes");
    expect(region).toHaveTextContent("no significa que todo vaya bien");
    expect(region).toHaveTextContent("Faltan observaciones recientes de Sueño y Ánimo");
    expect(region).toHaveTextContent("no se interpreta como cero");
    expect(region).toHaveTextContent("Aún insuficiente");
    expect(region).toHaveTextContent("La ausencia de una señal no demuestra ausencia de riesgo.");
    expect(region).not.toHaveTextContent(/sin riesgo|no hay riesgo|0%/i);
    expect(region).not.toHaveTextContent("insufficient_data");
    expect(within(region).queryByText("0")).not.toBeInTheDocument();
  });

  it("keeps No ahora and refreshes the comparison after a check-in", async () => {
    let phase: "before" | "after" = "before";
    vi.mocked(api.get).mockImplementation(async (path: string) => {
      if (path.startsWith("/api/v1/state")) return phase === "before" ? insufficientState : calculatedState;
      if (path.startsWith("/api/v1/timeline")) return { points: [] };
      if (path.startsWith("/api/v1/assignments")) return [];
      throw new Error(`unexpected ${path}`);
    });
    vi.mocked(api.post).mockImplementation(async () => {
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
    expect(region).not.toHaveTextContent("Todavía no hay una comparación con tu línea de base");
    expect(region).not.toHaveTextContent("Nivel 4");
  });
});
