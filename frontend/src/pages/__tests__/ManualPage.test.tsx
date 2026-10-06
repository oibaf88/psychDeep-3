import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";
import ManualPage from "../ManualPage";

function renderManual() {
  return render(
    <MemoryRouter>
      <ManualPage />
    </MemoryRouter>,
  );
}

describe("ManualPage", () => {
  it("names the running inference connection and the memory tab", async () => {
    const user = userEvent.setup();
    renderManual();

    expect(screen.getAllByText(/Anthropic, Codex \/ ChatGPT o el modelo cargado en LM Studio/).length).toBeGreaterThan(0);
    expect(screen.queryByText(/Gemma 2/)).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "2. Roles y permisos" }));
    expect(screen.getByText(/solicitudes pendientes y las hechas/)).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "9. La ficha, pestaña a pestaña" }));
    expect(screen.getByText("Memoria y lectura")).toBeInTheDocument();
    expect(screen.getByText(/no cambia el nivel de riesgo/)).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "12. Privacidad y auditoría" }));
    expect(screen.getByText(/Mis modelos/)).toBeInTheDocument();
    expect(screen.queryByText(/Gemma 2/)).not.toBeInTheDocument();
  });
});
