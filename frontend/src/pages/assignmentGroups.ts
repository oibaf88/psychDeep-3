import { ASSIGNMENT_STATUS_LABELS } from "../api";

export interface AssignmentStatusRow {
  status: string;
  professional_display_name?: string | null;
  professional_email?: string | null;
}

export function partitionAssignments<T extends { status: string }>(rows: T[]) {
  return {
    pending: rows.filter((row) => row.status === "pending"),
    done: rows.filter((row) => row.status !== "pending"),
  };
}

export function professionalLinkLabel(row: AssignmentStatusRow) {
  const name = row.professional_display_name || row.professional_email || "Profesional";
  const status = ASSIGNMENT_STATUS_LABELS[row.status] || row.status;
  return `${name} (${status})`;
}

export function joinAssignmentLabels(rows: AssignmentStatusRow[]) {
  if (rows.length === 0) return "ninguna";
  return rows.map(professionalLinkLabel).join("; ");
}
