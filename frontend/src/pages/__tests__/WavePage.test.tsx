import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import WavePage from "../WavePage";

vi.mock("../../api", () => ({
  api: {
    get: vi.fn().mockResolvedValue({ safe_grounding_alternatives: ["Siente los pies en el suelo"] }),
  },
}));

describe("WavePage", () => {
  beforeEach(() => {
    vi.stubGlobal("requestAnimationFrame", () => 1);
    vi.stubGlobal("cancelAnimationFrame", () => undefined);
  });

  it("keeps the Spanish urge-surfing copy and the 90s observe ride", async () => {
    const user = userEvent.setup();
    const { container } = render(<WavePage />);

    expect(screen.getByRole("heading", { name: "Metafora de la Ola" })).toBeInTheDocument();
    expect(
      screen.getByText("Ajusta la intensidad inicial y pulsa «Observar la ola» para verla subir, hacer pico y bajar."),
    ).toBeInTheDocument();

    const slider = screen.getByRole("slider", { name: "Intensidad de la urgencia de 0 a 10" });
    expect(slider).toBeEnabled();

    await user.click(screen.getByRole("button", { name: "Observar la ola (~90 s)" }));

    expect(screen.getByRole("button", { name: "Pausar" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Detener" })).toBeInTheDocument();
    expect(slider).toBeDisabled();
    expect(screen.getByRole("progressbar", { name: "Progreso de la observación de la ola" })).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Pausar" }));
    expect(screen.getByText("Pausa. La ola se queda donde está hasta que sigas.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Seguir observando" })).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Detener" }));
    expect(screen.getByRole("button", { name: "Observar la ola (~90 s)" })).toBeInTheDocument();
    expect(slider).toBeEnabled();

    const paths = container.querySelectorAll(".wave-back, .wave-mid, .wave-front, .wave-foam");
    expect(paths).toHaveLength(4);
    paths.forEach((path) => expect(path.getAttribute("d")?.length ?? 0).toBeGreaterThan(20));
  });
});
