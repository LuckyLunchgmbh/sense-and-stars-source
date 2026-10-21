export interface RecoveryLink {
  token: string | null;
}

export function parseRecoveryLink(hash: string): RecoveryLink | null {
  const [route, ...query] = hash.replace(/^#/, "").split("?");
  if (route !== "reset-password") return null;
  const tokens = new URLSearchParams(query.join("?")).getAll("token");
  const token = tokens.length === 1 ? tokens[0] : "";
  return { token: /^[A-Za-z0-9_-]{43}$/.test(token) ? token : null };
}

export function recoveryRequestError(status?: number) {
  if (status === 503)
    return "Der Dienst ist vorübergehend nicht verfügbar. Deine Anfrage konnte nicht zuverlässig bestätigt werden. Prüfe dein E-Mail-Postfach und versuche es bei Bedarf später erneut.";
  if (status === 429)
    return "Es gab gerade zu viele Anfragen. Bitte versuche es später erneut. Bereits erhaltene Links kannst du weiterhin öffnen.";
  return "Die Anfrage konnte gerade nicht abgeschlossen werden. Prüfe deine Internetverbindung und versuche es noch einmal.";
}

// Capture once before React mounts; StrictMode may run state initializers twice.
export function captureRecoveryLink(
  location: Pick<Location, "hash" | "pathname" | "search">,
  history: Pick<History, "state" | "replaceState">,
): RecoveryLink | null {
  const link = parseRecoveryLink(location.hash);
  if (link) {
    history.replaceState(
      history.state,
      "",
      `${location.pathname}${location.search}#reset-password`,
    );
  }
  return link;
}

export function validateRecoveryPassword(
  password: string,
  confirmation: string,
) {
  const length = Array.from(password).length;
  if (length < 12 || length > 256)
    return "Dein neues Passwort braucht 12 bis 256 Zeichen. Drei einfache Wörter können helfen, es dir zu merken.";
  if (password !== confirmation)
    return "Die beiden Passwörter stimmen noch nicht überein. Bitte prüfe sie noch einmal.";
  return null;
}
