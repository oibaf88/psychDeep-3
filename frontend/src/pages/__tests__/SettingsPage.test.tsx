import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import SettingsPage from "../SettingsPage";
import { api } from "../../api";

vi.mock("../../api", async () => {
  const actual = await vi.importActual<typeof import("../../api")>("../../api");
  return {
    ...actual,
    api: { get: vi.fn(), put: vi.fn(), post: vi.fn(), del: vi.fn() },
  };
});

const status = {
  configured: true,
  provider: "openai_compatible" as const,
  max_tokens: 4096,
  timeout_seconds: 120,
  local_available: true,
  lm_api_key_configured: true,
  anthropic_allowed: true,
  openai_allowed: true,
  local_llm_usable: true,
  local_models: [{ id: "prism-ml/bonsai-27b", loaded: true }],
  effective_local_model: "prism-ml/bonsai-27b",
  chat_model: "",
};

describe("SettingsPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(api.get).mockResolvedValue(status);
  });

  it("offers local, Anthropic and Codex/ChatGPT without a model picker", async () => {
    render(<SettingsPage />);

    expect(await screen.findByRole("option", { name: "Local" })).toBeInTheDocument();
    expect(screen.getByRole("option", { name: "Anthropic" })).toBeInTheDocument();
    expect(screen.getByRole("option", { name: "Codex / ChatGPT" })).toBeInTheDocument();
    expect(screen.getByText("API key de LM Studio")).toBeInTheDocument();
    expect(screen.getByPlaceholderText("Configurada · deja vacío para conservar")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Probar conexión" })).toBeInTheDocument();
    expect(screen.getByText(/modelo que tengas cargado en tu ordenador/i)).toBeInTheDocument();

    expect(screen.queryByRole("option", { name: /modelo que esté cargado/i })).not.toBeInTheDocument();
    expect(screen.queryByText(/Modelo de LM Studio/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/Modelo de conversación/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/Máximo de tokens/i)).not.toBeInTheDocument();
    expect(screen.queryByText("prism-ml/bonsai-27b")).not.toBeInTheDocument();
    expect(screen.queryByText(/Si hay varios, elige uno/i)).not.toBeInTheDocument();
  });
});
