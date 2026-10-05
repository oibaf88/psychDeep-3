import type { ReactNode } from "react";
import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { api, PatientTimelineOut } from "../../api";
import PatientDashboard from "../PatientDashboard";
import TrendsPage from "../TrendsPage";

vi.mock("recharts", () => ({
  ResponsiveContainer: ({ children, height }: { children?: ReactNode; height?: number }) => (
    <div data-testid="responsive-container" data-height={height}>{children}</div>
  ),
  LineChart: ({
    children,
    data = [],
    margin,
  }: {
    children?: ReactNode;
    data?: Array<{ date?: string }>;
    margin?: Record<string, number>;
  }) => (
    <div
      data-testid="line-chart"
      data-first-date={data[0]?.date}
      data-last-date={data[data.length - 1]?.date}
      data-margin={JSON.stringify(margin)}
    >
      {children}
    </div>
  ),
  Line: ({
    dataKey,
    dot,
    strokeDasharray,
    yAxisId,
  }: {
    dataKey: string;
    dot?: { r?: number };
    strokeDasharray?: string;
    yAxisId?: string;
  }) => (
    <span
      data-testid={`line-${dataKey}`}
      data-axis={yAxisId}
      data-dot-radius={dot?.r}
      data-stroke-dasharray={strokeDasharray}
    />
  ),
  CartesianGrid: () => null,
  Legend: () => null,
  Tooltip: () => null,
  XAxis: () => null,
  YAxis: () => null,
}));

const timeline: PatientTimelineOut = {
  window_days: 30,
  points: [
    { date: "2026-10-02", mood: 7, craving: 2, sleep_hours: 6.5, self_efficacy: 8 },
    { date: "2026-10-01", mood: 6, craving: 3, sleep_hours: 7, self_efficacy: 7 },
  ],
};

function mockPatientApi() {
  return vi.spyOn(api, "get").mockImplementation(async <T,>(path: string): Promise<T> => {
    if (path.startsWith("/api/v1/timeline")) return structuredClone(timeline) as T;
    if (path === "/api/v1/assignments/mine") return [] as T;
    if (path === "/api/v1/baselines/current") {
      return { status: "insufficient_data", baseline: null } as T;
    }
    if (path.startsWith("/api/v1/changes")) return [] as T;
    throw new Error(`Unexpected test request: ${path}`);
  });
}

afterEach(() => {
  vi.restoreAllMocks();
});

describe("patient timeline views", () => {
  it("keeps the Hoy chart contract and latest-value summary", async () => {
    mockPatientApi();

    render(
      <MemoryRouter>
        <PatientDashboard />
      </MemoryRouter>,
    );

    await screen.findByText("6/10");
    expect(screen.getByText("3/10")).toBeInTheDocument();
    expect(screen.getByText("7 h")).toBeInTheDocument();
    expect(screen.getByTestId("responsive-container")).toHaveAttribute("data-height", "300");
    expect(screen.getByTestId("line-chart")).toHaveAttribute(
      "data-margin",
      JSON.stringify({ top: 8, right: 8, bottom: 4, left: -16 }),
    );
    expect(screen.getByTestId("line-chart")).toHaveAttribute("data-first-date", "2026-10-02");
    for (const key of ["mood", "craving", "self_efficacy"]) {
      expect(screen.getByTestId(`line-${key}`)).toHaveAttribute("data-axis", "left");
      expect(screen.getByTestId(`line-${key}`)).toHaveAttribute("data-dot-radius", "2.5");
    }
    expect(screen.getByTestId("line-sleep_hours")).toHaveAttribute("data-axis", "sleep");
    expect(screen.getByTestId("line-sleep_hours")).toHaveAttribute("data-dot-radius", "2");
    expect(screen.getByTestId("line-sleep_hours")).toHaveAttribute("data-stroke-dasharray", "5 3");
  });

  it("keeps Tendencias sorted chronologically with its larger chart", async () => {
    mockPatientApi();

    render(
      <MemoryRouter>
        <TrendsPage />
      </MemoryRouter>,
    );

    await waitFor(() => expect(screen.getByTestId("line-chart")).toBeInTheDocument());
    expect(screen.getByText("7/10")).toBeInTheDocument();
    expect(screen.getByText("2/10")).toBeInTheDocument();
    expect(screen.getByText("6.5 h")).toBeInTheDocument();
    expect(screen.getByTestId("responsive-container")).toHaveAttribute("data-height", "340");
    expect(screen.getByTestId("line-chart")).toHaveAttribute(
      "data-margin",
      JSON.stringify({ top: 8, right: 12, bottom: 8, left: -10 }),
    );
    expect(screen.getByTestId("line-chart")).toHaveAttribute("data-first-date", "2026-10-01");
    expect(screen.getByTestId("line-chart")).toHaveAttribute("data-last-date", "2026-10-02");
    for (const key of ["mood", "craving", "self_efficacy"]) {
      expect(screen.getByTestId(`line-${key}`)).toHaveAttribute("data-dot-radius", "2");
    }
    expect(screen.getByTestId("line-sleep_hours")).toHaveAttribute("data-dot-radius", "2");
    expect(screen.getByRole("heading", { name: "Señales de cambio" })).toBeInTheDocument();
    expect(screen.getByText(/falta de cálculo no significa que todo vaya bien/)).toBeInTheDocument();
    expect(screen.queryByText(/sin riesgo|no hay riesgo/i)).not.toBeInTheDocument();
    expect(screen.queryByText("0%")).not.toBeInTheDocument();
    expect(screen.queryByText(/nivel de alerta\s*\d/i)).not.toBeInTheDocument();
  });
});
