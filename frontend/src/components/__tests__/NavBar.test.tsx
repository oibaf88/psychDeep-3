import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { UserOut, UserRole } from "../../api";
import NavBar from "../NavBar";

const authState = vi.hoisted(() => ({
  user: null as UserOut | null,
  logout: vi.fn(),
}));

vi.mock("../../auth/AuthContext", () => ({
  useAuth: () => authState,
}));

const roleLinks: Record<UserRole, Array<[string, string]>> = {
  patient: [
    ["Hoy", "/"],
    ["Tendencias", "/trends"],
    ["Regular", "/wave"],
    ["Diario", "/diary"],
    ["Plan", "/safety-plan"],
    ["Compartir", "/sharing"],
    ["Chat", "/chat"],
    ["Avisos", "/notifications"],
  ],
  therapist: [
    ["Pacientes", "/professional"],
    ["Alertas", "/professional/alerts"],
    ["Copiloto", "/professional/copilot"],
    ["Asignaciones", "/professional/assignments"],
    ["Manual", "/professional/manual"],
    ["Avisos", "/notifications"],
  ],
  supervisor: [
    ["Pacientes", "/professional"],
    ["Alertas", "/professional/alerts"],
    ["Copiloto", "/professional/copilot"],
    ["Asignaciones", "/professional/assignments"],
    ["Auditoría", "/professional/audit"],
    ["Manual", "/professional/manual"],
    ["Avisos", "/notifications"],
  ],
  admin_clinical: [
    ["Roster", "/professional"],
    ["Usuarios", "/professional/users"],
    ["Asignaciones", "/professional/assignments"],
    ["Auditoría", "/professional/audit"],
    ["Manual", "/professional/manual"],
    ["Avisos", "/notifications"],
  ],
};

function user(role: UserRole): UserOut {
  return {
    id: `user-${role}`,
    email: `${role}@example.test`,
    display_name: "Persona de prueba",
    role,
    locale: "es-ES",
  };
}

afterEach(() => {
  authState.user = null;
  authState.logout.mockReset();
});

describe("NavBar role navigation", () => {
  for (const role of Object.keys(roleLinks) as UserRole[]) {
    it(`keeps the ordered ${role} links`, () => {
      authState.user = user(role);
      render(
        <MemoryRouter>
          <NavBar />
        </MemoryRouter>,
      );

      const links = screen.getAllByRole("link").map((link) => [
        link.textContent,
        link.getAttribute("href"),
      ]);
      const account = [["Mi cuenta", "/account"]] as Array<[string, string]>;
      const models = role === "admin_clinical" ? [["Mis modelos", "/settings"] as [string, string]] : [];
      expect(links).toEqual([...roleLinks[role], ...account, ...models]);
      expect(screen.getByRole("button", { name: "Salir" })).toBeInTheDocument();
    });
  }

  it("keeps the unauthenticated login link", () => {
    render(
      <MemoryRouter>
        <NavBar />
      </MemoryRouter>,
    );

    expect(screen.getByRole("link", { name: "Entrar" })).toHaveAttribute("href", "/login");
    expect(screen.queryByRole("button", { name: "Salir" })).not.toBeInTheDocument();
  });
});
