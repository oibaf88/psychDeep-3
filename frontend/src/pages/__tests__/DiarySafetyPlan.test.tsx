import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import { api, formatDateTime, formatDay } from "../../api";
import DiaryPage from "../DiaryPage";
import SafetyPlanPage from "../SafetyPlanPage";

afterEach(() => vi.restoreAllMocks());

function renderIn(node: JSX.Element) {
  return render(<MemoryRouter>{node}</MemoryRouter>);
}

describe("Diario: consent-aware copy", () => {
  it("does not claim analysis without linguistic-analysis consent", async () => {
    vi.spyOn(api, "get").mockImplementation(async <T,>(path: string): Promise<T> => {
      if (path === "/api/v1/diary") return [] as T;
      if (path === "/api/v1/consents") return [{ consent_type: "data_processing", granted: true }] as T;
      throw new Error(path);
    });
    renderIn(<DiaryPage />);
    expect(await screen.findByText(/El análisis lingüístico no está autorizado/)).toBeInTheDocument();
    expect(screen.queryByText(/Se analiza para ayudarte/)).not.toBeInTheDocument();
    expect(await screen.findByText("Todavía no has escrito ninguna entrada.")).toBeInTheDocument();
  });

  it("says analysis happens only when consent is granted", async () => {
    vi.spyOn(api, "get").mockImplementation(async <T,>(path: string): Promise<T> => {
      if (path === "/api/v1/diary") return [] as T;
      if (path === "/api/v1/consents") return [{ consent_type: "linguistic_analysis", granted: true, revoked_at: null }] as T;
      throw new Error(path);
    });
    renderIn(<DiaryPage />);
    expect(await screen.findByText(/Has autorizado el análisis lingüístico/)).toBeInTheDocument();
  });

  it("revoked consent is not analysis", async () => {
    vi.spyOn(api, "get").mockImplementation(async <T,>(path: string): Promise<T> => {
      if (path === "/api/v1/diary") return [] as T;
      if (path === "/api/v1/consents") return [{ consent_type: "linguistic_analysis", granted: true, revoked_at: "2026-10-01T00:00:00Z" }] as T;
      throw new Error(path);
    });
    renderIn(<DiaryPage />);
    expect(await screen.findByText(/no está autorizado/)).toBeInTheDocument();
  });

  it("shows an error state when entries cannot be loaded", async () => {
    vi.spyOn(api, "get").mockRejectedValue(new Error("boom"));
    renderIn(<DiaryPage />);
    expect(await screen.findByRole("alert")).toHaveTextContent("No se pudieron cargar tus entradas");
    expect(screen.getByText(/No se pudo comprobar/)).toBeInTheDocument();
  });
});

describe("Plan de seguridad: national lines always, local ones labelled", () => {
  it("keeps 024 and 112 even when every request fails", async () => {
    vi.spyOn(api, "get").mockRejectedValue(new Error("offline"));
    renderIn(<SafetyPlanPage />);
    expect(await screen.findByRole("alert")).toHaveTextContent("No se pudo cargar tu plan");
    const national = screen.getByRole("heading", { name: /Ayuda inmediata/ }).parentElement!;
    expect(national).toHaveTextContent("Línea 024");
    expect(national).toHaveTextContent("112");
    expect(screen.queryByText(/Madrid/)).not.toBeInTheDocument();
  });

  it("labels local resources with their configured region", async () => {
    vi.spyOn(api, "get").mockImplementation(async <T,>(path: string): Promise<T> => {
      if (path === "/api/v1/safety-plan") return { id: "p", updated_at: "2026-10-01T00:00:00Z" } as T;
      return {
        local_region: "Comunidad de Madrid",
        resources: [
          { name: "Línea 024", description: "x", contact: "024", scope: "nacional" },
          { name: "112", description: "y", contact: "112", scope: "nacional" },
          { name: "Red CAD", description: "z", contact: "https://example.org", scope: "local", region: "Comunidad de Madrid" },
        ],
      } as T;
    });
    renderIn(<SafetyPlanPage />);
    expect(await screen.findByRole("heading", { name: "Recursos locales · Comunidad de Madrid" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "024" })).toHaveAttribute("href", "tel:024");
  });
});

describe("es-ES dates", () => {
  it("formats days and date-times day-first", () => {
    expect(formatDay("2026-09-20")).toBe("20/09/2026");
    expect(formatDateTime("2026-09-20T10:05:00")).toMatch(/^20\/09\/2026,? 10:05$/);
  });
});
