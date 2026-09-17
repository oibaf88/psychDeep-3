import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import { MemoryRouter } from "react-router-dom";
import SharingPage from "../SharingPage";

describe("SharingPage", () => {
  const renderWithRouter = (ui: React.ReactElement) => {
    return render(<MemoryRouter>{ui}</MemoryRouter>);
  };

  it("renders the SharingPage and correctly displays links", () => {
    renderWithRouter(<SharingPage />);

    // Verify title and descriptions
    expect(screen.getByText("Compartir")).toBeInTheDocument();
    expect(screen.getByText("Profesionales vinculados")).toBeInTheDocument();
    expect(screen.getByText("Consentimientos")).toBeInTheDocument();
    expect(screen.getByText("Preparar consulta")).toBeInTheDocument();

    // Verify the links
    const assignmentsLink = screen.getByRole("link", { name: "Gestionar vinculaciones" });
    expect(assignmentsLink).toBeInTheDocument();
    expect(assignmentsLink).toHaveAttribute("href", "/assignments");

    const consentsLink = screen.getByRole("link", { name: "Gestionar consentimientos" });
    expect(consentsLink).toBeInTheDocument();
    expect(consentsLink).toHaveAttribute("href", "/consents");

    const trendsLink = screen.getByRole("link", { name: "Ver tendencias" });
    expect(trendsLink).toBeInTheDocument();
    expect(trendsLink).toHaveAttribute("href", "/trends");

    const factsLink = screen.getByRole("link", { name: "Revisar hechos" });
    expect(factsLink).toBeInTheDocument();
    expect(factsLink).toHaveAttribute("href", "/facts");
  });
});
