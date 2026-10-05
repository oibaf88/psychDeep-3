import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter } from "react-router-dom";
import type { UserOut } from "../../api";
import { api } from "../../api";
import AssignmentsPage from "../AssignmentsPage";

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

function admin(): UserOut {
  return {
    id: "admin-1",
    email: "admin@example.com",
    display_name: "Admin Clínico",
    role: "admin_clinical",
    locale: "es",
  };
}

describe("AssignmentsPage for the clinical admin", () => {
  beforeEach(() => {
    currentUser = admin();
    vi.clearAllMocks();
  });

  it("shows pending and done links for the selected patient", async () => {
    vi.mocked(api.get).mockResolvedValue([
      {
        id: "pending-1",
        patient_id: "patient-1",
        professional_id: "therapist-1",
        status: "pending",
        requested_at: "2026-10-01T10:00:00",
        patient_display_name: "Paciente Con Vínculos",
        professional_display_name: "Dra. Pendiente",
        professional_email: "pendiente@example.com",
      },
      {
        id: "done-1",
        patient_id: "patient-1",
        professional_id: "therapist-2",
        status: "active",
        requested_at: "2026-09-01T10:00:00",
        patient_display_name: "Paciente Con Vínculos",
        professional_display_name: "Dr. Hecho",
        professional_email: "hecho@example.com",
      },
    ]);

    render(
      <MemoryRouter initialEntries={["/professional/assignments?patient=patient-1&nombre=Paciente%20Con%20V%C3%ADnculos"]}>
        <AssignmentsPage />
      </MemoryRouter>,
    );

    expect(await screen.findByRole("heading", { name: "Pendientes" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Hechas" })).toBeInTheDocument();
    const pending = screen.getByRole("region", { name: "Pendientes" });
    const done = screen.getByRole("region", { name: "Hechas" });
    expect(pending).toHaveTextContent("Dra. Pendiente");
    expect(pending).toHaveTextContent("Pendiente de aceptación");
    expect(done).toHaveTextContent("Dr. Hecho");
    expect(done).toHaveTextContent("Activa");
    expect(pending).not.toHaveTextContent("Dr. Hecho");
    expect(done).not.toHaveTextContent("Dra. Pendiente");
    await waitFor(() => {
      expect(api.get).toHaveBeenCalledWith("/api/v1/assignments/mine?patient_id=patient-1");
    });
  });

  it("says when that patient has neither pending nor done assignments", async () => {
    vi.mocked(api.get).mockResolvedValue([]);

    render(
      <MemoryRouter initialEntries={["/professional/assignments?patient=patient-2&nombre=Paciente%20Sin%20V%C3%ADnculos"]}>
        <AssignmentsPage />
      </MemoryRouter>,
    );

    expect(
      await screen.findByText("Este paciente no tiene asignaciones clínicas pendientes ni hechas."),
    ).toBeInTheDocument();
    expect(screen.getByText("Ninguna pendiente.")).toBeInTheDocument();
    expect(screen.getByText("Ninguna hecha.")).toBeInTheDocument();
  });
});
