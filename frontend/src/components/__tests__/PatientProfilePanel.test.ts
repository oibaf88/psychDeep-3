import { describe, expect, it } from "vitest";
import { formatLongitudinalItem } from "../PatientProfilePanel";

describe("formatLongitudinalItem", () => {
  it("prefers a string description over other fields", () => {
    expect(formatLongitudinalItem({ description: "Patrón provisional", pattern: "otra" }, ["description", "pattern"]))
      .toBe("Patrón provisional");
  });

  it("does not return objects as React children", () => {
    expect(formatLongitudinalItem({ description: { unexpected: true }, pattern: "patrón" }, ["description", "pattern"]))
      .toBe("patrón");
  });

  it("serializes a record when no preferred string is available", () => {
    expect(formatLongitudinalItem({ extra: 1 }, ["description", "pattern"])).toBe('{"extra":1}');
  });
});
