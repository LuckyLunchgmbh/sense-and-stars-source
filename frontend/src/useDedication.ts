import {
  useEffect,
  useLayoutEffect,
  useReducer,
  useRef,
  useState,
} from "react";
import { api, ApiError } from "./api";
import {
  dedicationForScope,
  dedicationFailureType,
  dedicationReducer,
  initialDedicationState,
  parseDedicationResponse,
} from "./dedicationState";

async function withDeadline<T>(request: Promise<T>): Promise<T> {
  let timer: ReturnType<typeof setTimeout> | undefined;
  try {
    return await Promise.race([
      request,
      new Promise<never>((_, reject) => {
        timer = setTimeout(
          () => reject(new Error("Zeitüberschreitung")),
          12000,
        );
      }),
    ]);
  } finally {
    if (timer) clearTimeout(timer);
  }
}

export function useDedication(scope: string | null) {
  const [state, dispatch] = useReducer(
    dedicationReducer,
    initialDedicationState(),
  );
  const [reload, setReload] = useState({
    revision: 0,
    scope: null as string | null,
    manual: false,
  });
  const sequence = useRef(0);
  const currentScope = useRef(scope);
  const mounted = useRef(true);
  const saving = useRef<{ scope: string; requestId: number } | null>(null);
  useLayoutEffect(() => {
    currentScope.current = scope;
    saving.current = null;
  }, [scope]);
  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
    };
  }, []);
  useEffect(() => {
    let active = true;
    const requestId = ++sequence.current;
    dispatch({ type: "load", scope, requestId });
    if (!scope) return;
    withDeadline(api<unknown>("/dedication"))
      .then(parseDedicationResponse)
      .then((response) => {
        if (active)
          dispatch({
            type: "loaded",
            scope,
            requestId,
            response,
            manual: reload.scope === scope && reload.manual,
          });
      })
      .catch((reason) => {
        if (active)
          dispatch({
            type: dedicationFailureType(
              reason instanceof ApiError ? reason.status : undefined,
              "load",
            ),
            scope,
            requestId,
          });
      });
    return () => {
      active = false;
    };
  }, [scope, reload]);

  const current = dedicationForScope(state, scope);
  function retry() {
    if (!scope) return;
    setReload((previous) => ({
      revision: previous.revision + 1,
      scope,
      manual: true,
    }));
  }
  function open() {
    // Revalidate the session and current content version before reading again.
    retry();
  }
  async function dismiss() {
    if (!scope || !current.dedication) return;
    const requestId = current.requestId;
    if (
      saving.current?.scope === scope &&
      saving.current.requestId === requestId
    ) {
      dispatch({ type: "hide", scope, requestId });
      return;
    }
    const operation = { scope, requestId };
    saving.current = operation;
    dispatch({ type: "dismiss", scope, requestId });
    try {
      const result = await withDeadline(
        api<{ ok: boolean }>("/dedication/dismiss", {
          id: current.dedication.id,
          version: current.dedication.version,
        }),
      );
      if (!result.ok) throw new Error("Schließen nicht bestätigt");
      if (mounted.current && currentScope.current === scope)
        dispatch({ type: "dismissed", scope, requestId });
    } catch (reason) {
      if (mounted.current && currentScope.current === scope)
        dispatch({
          type: dedicationFailureType(
            reason instanceof ApiError ? reason.status : undefined,
            "dismiss",
          ),
          scope,
          requestId,
        });
    } finally {
      if (saving.current === operation) saving.current = null;
    }
  }
  return { state: current, retry, open, dismiss };
}

// Defer automatic dialogs while an ordinary practice/learning dialog is open.
export function useOtherDialogOpen() {
  const [open, setOpen] = useState(false);
  useEffect(() => {
    const update = () =>
      setOpen(
        !!document.querySelector(
          "dialog[open]:not(.dedication-modal):not(.tour-modal)",
        ),
      );
    update();
    const observer = new MutationObserver(update);
    observer.observe(document.body, {
      childList: true,
      subtree: true,
      attributes: true,
      attributeFilter: ["open"],
    });
    return () => observer.disconnect();
  }, []);
  return open;
}

export type DedicationController = ReturnType<typeof useDedication>;
