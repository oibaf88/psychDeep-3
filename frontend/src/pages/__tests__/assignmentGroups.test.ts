import { describe, expect, it } from "vitest";
import { joinAssignmentLabels, partitionAssignments } from "../assignmentGroups";

describe("assignment groups", () => {
  const rows = [
    { status: "pending", professional_display_name: "Dra. Pendiente" },
    { status: "active", professional_display_name: "Dr. Hecho" },
    { status: "ended", professional_email: "cierre@example.com" },
  ];

  it("keeps requests apart from assignments that were already made", () => {
    const groups = partitionAssignments(rows);
    expect(groups.pending.map((row) => row.status)).toEqual(["pending"]);
    expect(groups.done.map((row) => row.status)).toEqual(["active", "ended"]);
  });

  it("names the professional and the status, and says when a group is empty", () => {
    const groups = partitionAssignments(rows);
    expect(joinAssignmentLabels(groups.pending)).toBe("Dra. Pendiente (Pendiente de aceptación)");
    expect(joinAssignmentLabels(groups.done)).toBe("Dr. Hecho (Activa); cierre@example.com (Finalizada)");
    expect(joinAssignmentLabels([])).toBe("ninguna");
  });
});
