import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import PsychDeepLoader from "../PsychDeepLoader";

describe("PsychDeepLoader", () => {
  it("uses the repository-owned animated logo asset", () => {
    const { container } = render(<PsychDeepLoader label="Preparando respuesta…" />);
    const video = container.querySelector("video");
    const source = container.querySelector("source");

    expect(video).toBeInTheDocument();
    expect(video).toHaveAttribute("autoplay");
    expect(video).toHaveAttribute("loop");
    expect((video as HTMLVideoElement).muted).toBe(true);
    expect(video).toHaveAttribute("playsinline");
    expect(source).toHaveAttribute("src", "/moving%20psychDeep%20logo.mp4");
    expect(video).toHaveAttribute("poster", "/psychDeep%20logo.png");
    expect(screen.getByRole("status")).toHaveTextContent("Preparando respuesta…");
  });
});
