import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { MemoryRouter } from "react-router-dom";
import type { UserOut } from "../../api";
import NavBar from "../NavBar";

let currentUser: UserOut | null = null;

vi.mock("../../auth/AuthContext", () => ({
  useAuth: () => ({ user: currentUser, logout: vi.fn() }),
}));

function user(role: UserOut["role"]): UserOut {
  return {
    id: "1",
    email: `${role}@example.com`,
    display_name: "Persona",
    role,
    locale: "es",
  };
}

describe("NavBar model menu", () => {
  it("hides Mis modelos from patients, therapists and supervisors", () => {
    for (const role of ["patient", "therapist", "supervisor"] as const) {
      currentUser = user(role);
      const view = render(
        <MemoryRouter>
          <NavBar />
        </MemoryRouter>,
      );
      expect(screen.queryByRole("link", { name: "Mis modelos" })).not.toBeInTheDocument();
      view.unmount();
    }
  });

  it("shows Mis modelos only to the clinical administrator", () => {
    currentUser = user("admin_clinical");
    render(
      <MemoryRouter>
        <NavBar />
      </MemoryRouter>,
    );
    expect(screen.getByRole("link", { name: "Mis modelos" })).toHaveAttribute("href", "/settings");
  });
});
