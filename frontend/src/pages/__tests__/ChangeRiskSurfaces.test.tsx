import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { UserOut } from "../../api";
import { api } from "../../api";
import { StructuralScoreChart } from "../../components/ClinicalCharts";
import { LevelExplanationCard, StructuralExplanationCard } from "../../components/ClinicalExplain";
import AlertsPage from "../AlertsPage";
import CopilotPage from "../CopilotPage";

let currentUser: UserOut | null = null;

vi.mock("../../auth/AuthContext", () => ({
  useAuth: () => ({ user: currentUser, logout: vi.fn() }),
}));

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

vi.mock("../../components/CopilotPanel", () => ({
  default: () => <div>Copiloto de prueba</div>,
}));

describe("risk and change stay on their own surfaces", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    currentUser = {
      id: "therapist-1",
      email: "therapist@example.com",
      display_name: "Terapeuta",
      role: "therapist",
      locale: "es",
    };
  });

  it("does not describe the structural chart as the change signal", () => {
    render(<StructuralScoreChart points={[]} />);
    const note = screen.getByText("Cómo se lee:").closest("p");
    expect(note).toHaveTextContent(/no la señal de cambio canónica ni el nivel de alerta/);
    expect(note).toHaveTextContent(/no rellena un hueco con cero/);
    expect(note).not.toHaveTextContent(/sin cambio/i);
    expect(note).not.toHaveTextContent(/sin riesgo/i);
  });

  it("labels the risk card and the structural card as different from change", () => {
    render(
      <>
        <LevelExplanationCard
          explanation={{
            level: 4,
            level_label: "Nivel 4 · Revisión clínica urgente",
            level_meaning: "Prioridad máxima.",
            headline: "Nivel 4 por un texto.",
            driver_family: "senal_linguistica",
            driver_family_label: "Texto del paciente",
          }}
        />
        <StructuralExplanationCard
          explanation={{
            score: null,
            band: null,
            scale_note: "Entrada del motor. Un score alto nunca «sin riesgo».",
            summary: "Sin score del motor. Esa falta no es un cero.",
            variables: [],
            caveats: [],
          }}
        />
      </>,
    );
    expect(screen.getByText(/No es la señal de cambio respecto a la línea de base personal\./)).toBeInTheDocument();
    expect(
      screen.getByText(/No es la señal de cambio respecto a la línea de base personal ni el nivel de alerta\./),
    ).toBeInTheDocument();
    expect(screen.queryByText("0.00")).not.toBeInTheDocument();
  });

  it("shows canonical change beside the alert on the copilot picker", async () => {
    vi.mocked(api.get).mockResolvedValue([
      {
        id: "patient-2",
        display_name: "Paciente",
        email: "p@example.com",
        assignment_status: "active",
        open_alerts: 1,
        latest_alert_level: 3,
        latest_structural_score: 0.91,
        latest_confidence_band: "stable",
        longitudinal: {
          baseline: { status: "insufficient_data", baseline: null },
          changes: [
            {
              signal_id: "mood-1",
              feature: "mood",
              band: "insufficient_data",
              change: null,
            },
          ],
          limits: ["La ausencia de una señal de cambio no demuestra ausencia de riesgo."],
        },
      },
    ]);

    render(
      <MemoryRouter>
        <CopilotPage />
      </MemoryRouter>,
    );

    expect(await screen.findByText("N3 · Alarma profesional")).toBeInTheDocument();
    expect(screen.getByText("Datos insuficientes")).toBeInTheDocument();
    expect(screen.getByText("Banda del motor: estable")).toBeInTheDocument();
    expect(screen.getByText("0.91")).toBeInTheDocument();
    expect(screen.getByText(/no es una alerta/)).toBeInTheDocument();
    expect(screen.queryByText(/sin riesgo|no hay riesgo/i)).not.toBeInTheDocument();
    expect(screen.queryByText("0.00")).not.toBeInTheDocument();
  });

  it("does not treat an empty alert list as absence of change or risk", async () => {
    vi.mocked(api.get).mockResolvedValue([]);
    render(
      <MemoryRouter>
        <AlertsPage />
      </MemoryRouter>,
    );
    expect(await screen.findByText(/No muestra la señal de cambio/)).toBeInTheDocument();
    expect(screen.getByText("No hay alertas con ese filtro.")).toBeInTheDocument();
    expect(screen.queryByText(/sin riesgo|no hay riesgo/i)).not.toBeInTheDocument();
  });
});
