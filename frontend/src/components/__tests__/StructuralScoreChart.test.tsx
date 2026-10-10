import { render, screen } from "@testing-library/react";
import { beforeAll, describe, expect, it } from "vitest";
import type { StructuralPoint } from "../../api";
import { StructuralScoreChart, structuralVersionLabel, structuralVersionSegments } from "../ClinicalCharts";

function point(date: string, score: number | null, calculation_version: string | null): StructuralPoint {
  return { at: `${date}T10:00:00Z`, date, score, calculation_version };
}

const mixed: StructuralPoint[] = [
  point("2026-09-12", 0.7, null),
  point("2026-09-13", 0.72, null),
  point("2026-09-20", 0.65, "structural-v1"),
  point("2026-10-01", 0.5, "structural-v2"),
  point("2026-10-02", null, "structural-v2"),
  point("2026-10-03", 0.43, "structural-v2"),
];

beforeAll(() => {
  globalThis.ResizeObserver ??= class {
    observe() {}
    unobserve() {}
    disconnect() {}
  } as unknown as typeof ResizeObserver;
});

describe("StructuralScoreChart across calculation versions (bug 2)", () => {
  it("builds ordered version segments and never relabels unlabeled rows as v1", () => {
    const segments = structuralVersionSegments(mixed);
    expect(segments.map((s) => [s.version, s.start, s.end, s.count])).toEqual([
      ["sin-version", "2026-09-12", "2026-09-13", 2],
      ["structural-v1", "2026-09-20", "2026-09-20", 1],
      ["structural-v2", "2026-10-01", "2026-10-03", 2],
    ]);
    expect(structuralVersionLabel(null)).toBe("Sin versión registrada");
    expect(structuralVersionLabel("structural-v2")).toBe("structural-v2 · fórmula actual");
  });

  it("renders ONE chart with a version legend instead of one chart per version", () => {
    const { container } = render(<StructuralScoreChart points={mixed} />);
    expect(container.querySelectorAll(".recharts-responsive-container").length).toBe(1);
    const legend = screen.getByRole("list", { name: "Versiones de cálculo en la serie" });
    expect(legend).toHaveTextContent("Sin versión registrada");
    expect(legend).toHaveTextContent("structural-v1 · cálculo histórico");
    expect(legend).toHaveTextContent("structural-v2 · fórmula actual");
    expect(screen.getByText(/La línea vertical marca el cambio de fórmula/)).toBeInTheDocument();
    expect(screen.queryByText(/Cada versión tiene su propia gráfica/)).not.toBeInTheDocument();
  });

  it("shows the empty state when no score was stored, never a zero line", () => {
    render(<StructuralScoreChart points={[point("2026-10-01", null, "structural-v2")]} />);
    expect(screen.getByText("Todavía no hay datos suficientes para dibujar esta gráfica.")).toBeInTheDocument();
  });
});
