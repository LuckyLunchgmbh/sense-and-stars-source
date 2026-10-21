export interface Dedication {
  id: number;
  version: number;
  title: string;
  salutation: string;
  paragraphs: string[];
  closing: string;
  sender: string;
}

export interface DedicationResponse {
  dedication: Dedication | null;
  auto_open: boolean;
}

export interface DedicationState {
  scope: string | null;
  requestId: number;
  status: "idle" | "loading" | "ready" | "error" | "expired";
  dedication: Dedication | null;
  open: boolean;
  saving: boolean;
  loadError: string;
  dismissalError: string;
}

type ScopedAction = { scope: string; requestId: number };
export type DedicationAction =
  | { type: "load"; scope: string | null; requestId: number }
  | (ScopedAction & {
      type: "loaded";
      response: DedicationResponse;
      manual: boolean;
    })
  | (ScopedAction & {
      type:
        | "failed"
        | "expired"
        | "hide"
        | "dismiss"
        | "dismissed"
        | "dismiss-failed";
    });

export function initialDedicationState(
  scope: string | null = null,
): DedicationState {
  return {
    scope,
    requestId: 0,
    status: scope ? "loading" : "idle",
    dedication: null,
    open: false,
    saving: false,
    loadError: "",
    dismissalError: "",
  };
}

// Filtering during render prevents a previous account's content appearing while
// the new session's effect is still waiting to run.
export function dedicationForScope(
  state: DedicationState,
  scope: string | null,
) {
  return state.scope === scope ? state : initialDedicationState(scope);
}

export function dedicationBlocksTour(state: DedicationState) {
  return state.status === "loading" || state.status === "expired" || state.open;
}

export function dedicationFailureType(
  status: number | undefined,
  operation: "load" | "dismiss",
) {
  if (status === 401) return "expired";
  return operation === "load" ? "failed" : "dismiss-failed";
}

export function dedicationReducer(
  state: DedicationState,
  action: DedicationAction,
): DedicationState {
  if (action.type === "load")
    return {
      ...initialDedicationState(action.scope),
      requestId: action.requestId,
    };
  if (action.scope !== state.scope || action.requestId !== state.requestId)
    return state;
  switch (action.type) {
    case "loaded":
      return {
        ...state,
        status: "ready",
        dedication: action.response.dedication,
        open:
          !!action.response.dedication &&
          (action.manual || action.response.auto_open),
        loadError: "",
      };
    case "failed":
      return {
        ...state,
        status: "error",
        dedication: null,
        open: false,
        loadError:
          "Deine persönliche Nachricht konnte gerade nicht geladen werden. Du kannst deinen Raum weiter nutzen und es später erneut versuchen.",
      };
    case "expired":
      return {
        ...initialDedicationState(state.scope),
        requestId: state.requestId,
        status: "expired",
      };
    case "hide":
      return { ...state, open: false };
    case "dismiss":
      return state.dedication
        ? { ...state, open: false, saving: true, dismissalError: "" }
        : state;
    case "dismissed":
      return { ...state, saving: false, dismissalError: "" };
    case "dismiss-failed":
      return {
        ...state,
        saving: false,
        dismissalError:
          "Das Schließen deiner Nachricht konnte nicht gespeichert werden. Sie kann nach einem Neuladen wieder erscheinen. Dein Raum bleibt nutzbar.",
      };
  }
}

export function parseDedicationResponse(value: unknown): DedicationResponse {
  const invalid = () =>
    new Error("Die persönliche Nachricht konnte nicht gelesen werden.");
  if (!value || typeof value !== "object") throw invalid();
  const response = value as Record<string, unknown>;
  if (typeof response.auto_open !== "boolean") throw invalid();
  if (response.dedication === null) {
    if (response.auto_open) throw invalid();
    return { dedication: null, auto_open: false };
  }
  if (!response.dedication || typeof response.dedication !== "object")
    throw invalid();
  const entry = response.dedication as Record<string, unknown>;
  if (
    !Number.isSafeInteger(entry.id) ||
    (entry.id as number) < 1 ||
    !Number.isSafeInteger(entry.version) ||
    (entry.version as number) < 1 ||
    !["title", "salutation", "closing", "sender"].every(
      (key) => typeof entry[key] === "string" && (entry[key] as string).trim(),
    ) ||
    !Array.isArray(entry.paragraphs) ||
    !entry.paragraphs.length ||
    !entry.paragraphs.every(
      (paragraph) => typeof paragraph === "string" && paragraph.trim(),
    )
  )
    throw invalid();
  return {
    auto_open: response.auto_open,
    dedication: {
      id: entry.id as number,
      version: entry.version as number,
      title: entry.title as string,
      salutation: entry.salutation as string,
      paragraphs: entry.paragraphs as string[],
      closing: entry.closing as string,
      sender: entry.sender as string,
    },
  };
}
