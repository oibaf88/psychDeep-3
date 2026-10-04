import { render } from "@testing-library/react";
import { beforeAll, describe, expect, it, vi } from "vitest";
import { PatientTrajectoryChart } from "../ClinicalCharts";

beforeAll(() => {
  class ResizeObserverMock {
    observe() {}
    unobserve() {}
    disconnect() {}
  }
  vi.stubGlobal("ResizeObserver", ResizeObserverMock);
  vi.spyOn(Element.prototype, "getBoundingClientRect").mockImplementation(() => ({
    width: 800,
    height: 400,
    top: 0,
    left: 0,
    bottom: 400,
    right: 800,
    x: 0,
    y: 0,
    toJSON() {
      return {};
    },
  }));
});

describe("PatientTrajectoryChart", () => {
  it("keeps the patient series, axes and missing-value gaps", () => {
    const { container } = render(
      <div style={{ width: 800, height: 400 }}>
        <PatientTrajectoryChart
          points={[
            { date: "2026-09-01", mood: 6, craving: 2, sleep_hours: 7, self_efficacy: 5 },
            { date: "2026-09-02", mood: null, craving: 8, sleep_hours: null, self_efficacy: 4 },
          ]}
          height={300}
          margin={{ top: 8, right: 8, bottom: 4, left: -16 }}
          dotRadius={2.5}
          sleepDotRadius={2}
          formatSleepTicks
        />
      </div>,
    );

    const text = container.textContent ?? "";
    expect(text).toContain("Ánimo");
    expect(text).toContain("Craving");
    expect(text).toContain("Autoeficacia");
    expect(text).toContain("Sueño (h)");

    const mood = container.querySelector('path[name="Ánimo"]');
    const sleep = container.querySelector('path[name="Sueño (h)"]');
    expect(mood).toHaveAttribute("stroke", "#7ea8f7");
    expect(mood).toHaveAttribute("stroke-width", "2.5");
    expect(mood?.getAttribute("d") ?? "").toMatch(/Z$/);
    expect(sleep).toHaveAttribute("stroke", "#e9c982");
    expect(sleep).toHaveAttribute("stroke-width", "2");
    expect(container.querySelectorAll(".recharts-line")).toHaveLength(4);
  });
});
