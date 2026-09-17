import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { MemoryRouter } from "react-router-dom";
import ConsentsPage from "../ConsentsPage";
import { api } from "../../api";

// Mock the API calls
vi.mock("../../api", async () => {
  const actual = await vi.importActual("../../api");
  return {
    ...actual,
    api: {
      get: vi.fn(),
      post: vi.fn(),
    },
  };
});

describe("ConsentsPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  const renderWithRouter = (ui: React.ReactElement) => {
    return render(<MemoryRouter>{ui}</MemoryRouter>);
  };

  it("renders correctly with mocked consents", async () => {
    const mockConsents = [
      {
        id: "1",
        consent_type: "data_processing",
        granted: true,
        granted_at: new Date().toISOString(),
        revoked_at: null,
      },
    ];

    vi.mocked(api.get).mockResolvedValue(mockConsents);

    renderWithRouter(<ConsentsPage />);

    // Wait for the data to be loaded and rendered
    await waitFor(() => {
      expect(screen.getByText("Concedido")).toBeInTheDocument();
    });

    const notGranted = screen.getAllByText("No concedido / revocado");
    // 4 other types should not be granted
    expect(notGranted.length).toBe(4);

    expect(api.get).toHaveBeenCalledWith("/api/v1/consents");
  });

  it("handles revoking an active consent", async () => {
    const user = userEvent.setup();
    const mockConsents = [
      {
        id: "1",
        consent_type: "data_processing",
        granted: true,
        granted_at: new Date().toISOString(),
        revoked_at: null,
      },
    ];

    vi.mocked(api.get).mockResolvedValue(mockConsents);
    vi.mocked(api.post).mockResolvedValue({
      id: "2",
      consent_type: "data_processing",
      granted: false,
      granted_at: new Date().toISOString(),
      revoked_at: null,
    });

    renderWithRouter(<ConsentsPage />);

    // Wait for initial render
    await waitFor(() => {
      expect(screen.getByText("Revocar")).toBeInTheDocument();
    });

    // Click revoke button
    const revokeButton = screen.getByText("Revocar");
    await user.click(revokeButton);

    expect(api.post).toHaveBeenCalledWith("/api/v1/consents", {
      consent_type: "data_processing",
      granted: false,
    });

    await waitFor(() => {
      expect(
        screen.getByText("Consentimiento revocado. Las nuevas operaciones de esa finalidad se detendrán.")
      ).toBeInTheDocument();
    });
  });

  it("handles granting an inactive consent", async () => {
    const user = userEvent.setup();
    const mockConsents = [
      {
        id: "1",
        consent_type: "data_processing",
        granted: false,
        granted_at: new Date().toISOString(),
        revoked_at: new Date().toISOString(),
      },
    ];

    vi.mocked(api.get).mockResolvedValue(mockConsents);
    vi.mocked(api.post).mockResolvedValue({
      id: "2",
      consent_type: "data_processing",
      granted: true,
      granted_at: new Date().toISOString(),
      revoked_at: null,
    });

    renderWithRouter(<ConsentsPage />);

    await waitFor(() => {
      expect(screen.getAllByText("Conceder").length).toBeGreaterThan(0);
    });

    // Click the first grant button (data_processing)
    const grantButtons = screen.getAllByText("Conceder");
    await user.click(grantButtons[0]);

    expect(api.post).toHaveBeenCalledWith("/api/v1/consents", {
      consent_type: "data_processing",
      granted: true,
    });

    await waitFor(() => {
      expect(screen.getByText("Consentimiento concedido.")).toBeInTheDocument();
    });
  });
});
