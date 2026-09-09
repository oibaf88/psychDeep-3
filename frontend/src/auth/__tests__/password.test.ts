import { describe, expect, it } from "vitest";
import { newPasswordError } from "../password";

describe("newPasswordError", () => {
  it("accepts a 12-character password", () => {
    expect(newPasswordError("CorrectHorse")).toBeNull();
  });

  it("rejects passwords shorter than 12 characters", () => {
    expect(newPasswordError("short")).toBe("La contraseña debe tener al menos 12 caracteres.");
  });

  it("counts unicode graphemes, not UTF-16 code units", () => {
    expect(newPasswordError("🙂🙂🙂🙂🙂🙂🙂🙂🙂🙂🙂")).toBe("La contraseña debe tener al menos 12 caracteres.");
    expect(newPasswordError("🙂🙂🙂🙂🙂🙂🙂🙂🙂🙂🙂🙂")).toBeNull();
  });

  it("rejects passwords that exceed bcrypt's 72-byte limit", () => {
    expect(newPasswordError("á".repeat(73))).toMatch(/72 bytes/);
  });
});
