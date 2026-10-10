import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter } from "react-router-dom";
import type { UserOut } from "../../api";
import { api } from "../../api";
import ProfessionalDashboard from "../ProfessionalDashboard";

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

describe("ProfessionalDashboard assignment visibility", () => {
  beforeEach(() => {
    currentUser = {
      id: "admin-1",
      email: "admin@example.com",
      display_name: "Admin Clínico",
      role: "admin_clinical",
      locale: "es",
    } satisfies UserOut;
    vi.clearAllMocks();
  });

  it("shows pending and done links for a patient without clinical alert data", async () => {
    vi.mocked(api.get).mockResolvedValue([
      {
        id: "patient-1",
        display_name: "Paciente Con Vínculos",
        email: "paciente@example.com",
        assignment_status: "pending",
        open_alerts: 9,
        latest_alert_level: 4,
        latest_structural_score: 0.91,
        assignments: [
          {
            id: "pending-1",
            professional_id: "therapist-1",
            professional_display_name: "Dra. Pendiente",
            status: "pending",
            requested_at: "2026-10-01T10:00:00",
          },
          {
            id: "done-1",
            professional_id: "therapist-2",
            professional_display_name: "Dr. Hecho",
            status: "ended",
            requested_at: "2026-09-01T10:00:00",
          },
        ],
      },
    ]);

    render(
      <MemoryRouter>
        <ProfessionalDashboard />
      </MemoryRouter>,
    );

    expect(await screen.findByText("Dra. Pendiente (Pendiente de aceptación)")).toBeInTheDocument();
    expect(screen.getByText("Dr. Hecho (Finalizada)")).toBeInTheDocument();
    const href = screen.getByRole("link", { name: "Ver asignaciones" }).getAttribute("href") ?? "";
    const params = new URLSearchParams(href.split("?")[1]);
    expect(params.get("patient")).toBe("patient-1");
    expect(params.get("nombre")).toBe("Paciente Con Vínculos");
    expect(screen.queryByText("roster")).not.toBeInTheDocument();
    expect(screen.queryByText("N4")).not.toBeInTheDocument();
    expect(screen.queryByText("9")).not.toBeInTheDocument();
  });

  it("keeps a missing change apart from the alert level and the motor band", async () => {
    currentUser = {
      id: "therapist-1",
      email: "therapist@example.com",
      display_name: "Terapeuta",
      role: "therapist",
      locale: "es",
    };
    vi.mocked(api.get).mockResolvedValue([
      {
        id: "patient-2",
        display_name: "Paciente Con Cambio Ausente",
        email: "cambio@example.com",
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
              uncertainty: { baseline_n: 0, recent_n: 0 },
            },
          ],
          limits: ["La ausencia de una señal de cambio no demuestra ausencia de riesgo."],
        },
      },
    ]);

    render(
      <MemoryRouter>
        <ProfessionalDashboard />
      </MemoryRouter>,
    );

    expect(await screen.findByText("N3")).toBeInTheDocument();
    expect(screen.getByText("Comparación aún no calculada")).toBeInTheDocument();
    expect(screen.getByText("Banda del motor: estable")).toBeInTheDocument();
    expect(screen.getByText("0.91")).toBeInTheDocument();
    expect(screen.getByText(/no es una alerta/)).toBeInTheDocument();
    expect(screen.queryByText(/sin riesgo|no hay riesgo/i)).not.toBeInTheDocument();
    expect(screen.queryByText("0.00")).not.toBeInTheDocument();
    expect(screen.queryByText(/1\.00 = sin cambios/)).not.toBeInTheDocument();
  });
});
