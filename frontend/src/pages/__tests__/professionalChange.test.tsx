import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import LongitudinalChangePanel from "../../components/LongitudinalChangePanel";
import { dashboardChangeDetail, dashboardChangeHeadline } from "../professionalChange";
import { calculatedLongitudinal, migratedLongitudinal, partialLongitudinal } from "./longitudinalFixtures";

describe("professional change reading", () => {
  it("roster headline and detail come from the shared reading", () => {
    expect(dashboardChangeHeadline(calculatedLongitudinal)).toBe("Bastante distinto de su referencia personal");
    expect(dashboardChangeDetail(calculatedLongitudinal)).toContain("no es una alerta");
    expect(dashboardChangeHeadline(partialLongitudinal)).toBe("Comparación en 3 de 4 áreas");
    expect(dashboardChangeHeadline(migratedLongitudinal)).toBe("Comparación aún no calculada");
  });

  it("renders a values table: reference, recent, difference, direction, z, counts", () => {
    render(<LongitudinalChangePanel longitudinal={calculatedLongitudinal} />);
    expect(screen.getByRole("heading", { name: "Cambio respecto a su línea de base" })).toBeInTheDocument();
    const craving = screen.getByRole("rowheader", { name: /Craving/ }).closest("tr")!;
    const cells = within(craving).getAllByRole("cell").map((cell) => cell.textContent);
    expect(cells.slice(0, 5)).toEqual(["2,6", "6,7", "+4,1", "Más alto", "+4,1"]);
    expect(cells[5]).toContain("6 / 21");
    expect(screen.getByText(/Algoritmo: canonical-structural-v2/)).toBeInTheDocument();
    expect(screen.getAllByText(/reproducible desde las filas citadas/).length).toBe(4);
    expect(screen.getByText(/no demuestra ausencia de riesgo/)).toBeInTheDocument();
    expect(screen.queryByText(/N3|nivel de alerta 3|alerta N/)).not.toBeInTheDocument();
  });

  it("a missing area shows its reason and never a zero", () => {
    render(<LongitudinalChangePanel longitudinal={partialLongitudinal} />);
    const sleep = screen.getByRole("rowheader", { name: /Sueño/ }).closest("tr")!;
    expect(sleep).toHaveTextContent("Sin comparación calculada");
    expect(sleep).toHaveTextContent("no hay registros en los últimos 7 días (la referencia tiene 21)");
    expect(within(sleep).getAllByRole("cell")[2].textContent).toBe("—");
    expect(screen.getByText(/Falta la comparación en Sueño/)).toBeInTheDocument();
  });
});
