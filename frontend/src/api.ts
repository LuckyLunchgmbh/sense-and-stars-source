export class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.status = status;
  }
}
export async function api<T>(
  path: string,
  body?: unknown,
  method?: string,
): Promise<T> {
  const verb = method || (body === undefined ? "GET" : "POST");
  const response = await fetch("/api" + path, {
    method: verb,
    credentials: "same-origin",
    cache: "no-store",
    headers: {
      ...(body === undefined ? {} : { "Content-Type": "application/json" }),
      ...(verb === "GET" ? {} : { "X-Sense-And-Stars": "1" }),
    },
    ...(body === undefined ? {} : { body: JSON.stringify(body) }),
  });
  const json = await response.json().catch(() => ({}));
  if (!response.ok) {
    const detail = json.detail;
    const message =
      typeof detail === "string"
        ? detail
        : Array.isArray(detail)
          ? detail
              .map(
                (item: { msg?: string; loc?: string[] }) =>
                  `${item.loc?.slice(1).join(" · ") || "Eingabe"}: ${item.msg || "Bitte prüfen"}`,
              )
              .join(" · ")
          : "Die Anfrage konnte nicht abgeschlossen werden.";
    throw new ApiError(message, response.status);
  }
  return json as T;
}
export const dateFormat = (
  date: string,
  options: Intl.DateTimeFormatOptions = {
    day: "2-digit",
    month: "short",
    year: "numeric",
  },
) =>
  new Intl.DateTimeFormat("de-DE", {
    timeZone: "Europe/Berlin",
    ...options,
  }).format(new Date(date.length === 10 ? date + "T12:00:00" : date));
export const money = (cents: number) =>
  new Intl.NumberFormat("de-DE", { style: "currency", currency: "EUR" }).format(
    cents / 100,
  );
export const roleName = (role: string) =>
  ({
    admin: "Betreiber",
    practitioner: "Beratung",
    client: "Persönlicher Raum",
  })[role] || role;
export function localDateTime(value: string) {
  return new Intl.DateTimeFormat("sv-SE", {
    timeZone: "Europe/Berlin",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hourCycle: "h23",
  })
    .format(new Date(value))
    .replace(" ", "T");
}
export function nextAppointmentTime() {
  const today = localDateTime(new Date().toISOString()).slice(0, 10);
  const next = new Date(today + "T12:00:00Z");
  next.setUTCDate(next.getUTCDate() + 1);
  return next.toISOString().slice(0, 10) + "T10:00";
}
// Convert the explicitly promised practice local time, independent of device timezone.
export function toBerlinISO(value: string): string {
  if (!/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}$/.test(value))
    throw new Error("Bitte gib ein gültiges Datum und eine Uhrzeit ein.");
  const naive = Date.parse(value + "Z");
  const formatter = new Intl.DateTimeFormat("sv-SE", {
    timeZone: "Europe/Berlin",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hourCycle: "h23",
  });
  const matching: number[] = [];
  for (let offset = -720; offset <= 840; offset += 15) {
    const instant = naive - offset * 60000;
    if (formatter.format(new Date(instant)).replace(" ", "T") === value)
      matching.push(instant);
  }
  if (!matching.length)
    throw new Error(
      "Diese Berliner Ortszeit existiert wegen einer Zeitumstellung nicht. Wähle eine andere Uhrzeit.",
    );
  if (matching.length > 1)
    throw new Error(
      "Diese Berliner Ortszeit kommt wegen einer Zeitumstellung zweimal vor. Wähle einen eindeutig bestimmbaren Zeitpunkt.",
    );
  return new Date(matching[0]).toISOString();
}
