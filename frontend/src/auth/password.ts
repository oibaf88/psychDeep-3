export function newPasswordError(password: string): string | null {
  if (Array.from(password).length < 12) return "La contraseña debe tener al menos 12 caracteres.";
  if (new TextEncoder().encode(password).length > 72) {
    return "La contraseña es demasiado larga. Usa un máximo de 72 bytes; las tildes y los emojis pueden ocupar más de uno.";
  }
  return null;
}
