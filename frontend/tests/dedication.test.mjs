import assert from "node:assert/strict";
import test from "node:test";
import {
  initialDedicationState,
  dedicationReducer,
  dedicationForScope,
  dedicationBlocksTour,
  dedicationFailureType,
  parseDedicationResponse,
} from "../src/dedicationState.ts";
import { api, ApiError } from "../src/api.ts";

const letter = {
  id: 7,
  version: 2,
  title: "Ein synthetischer Brief",
  salutation: "Liebes Testkonto,",
  paragraphs: ["Dieser Testtext gehört ausschließlich zum Testkonto."],
  closing: "Viele Grüße",
  sender: "Testabsender",
};
const scope = "test-session-1";
function loading(session = scope, requestId = 1) {
  return dedicationReducer(initialDedicationState(), {
    type: "load",
    scope: session,
    requestId,
  });
}
function loaded(autoOpen = true) {
  return dedicationReducer(loading(), {
    type: "loaded",
    scope,
    requestId: 1,
    response: { dedication: letter, auto_open: autoOpen },
    manual: false,
  });
}

test("initial authentication waits for the personal start before showing the tour", () => {
  const pending = dedicationForScope(initialDedicationState(), scope);
  assert.equal(pending.dedication, null);
  assert.equal(dedicationBlocksTour(pending), true);
  assert.equal(dedicationBlocksTour(loading()), true);
});

test("a new-session letter opens before the tour and a close leaves practice usable", () => {
  const state = loaded();
  assert.equal(state.open, true);
  assert.equal(dedicationBlocksTour(state), true);
  const dismissed = dedicationReducer(state, {
    type: "dismiss",
    scope,
    requestId: 1,
  });
  assert.equal(dismissed.open, false);
  assert.equal(dismissed.saving, true);
  assert.equal(dedicationBlocksTour(dismissed), false);
  const persisted = dedicationReducer(dismissed, {
    type: "dismissed",
    scope,
    requestId: 1,
  });
  assert.equal(persisted.saving, false);
  assert.equal(persisted.dismissalError, "");
});

test("reload honors dismissal and settings revalidates the letter before reopening", () => {
  const state = loaded(false);
  assert.equal(state.open, false);
  assert.equal(dedicationBlocksTour(state), false);
  const checking = dedicationReducer(state, {
    type: "load",
    scope,
    requestId: 2,
  });
  assert.equal(checking.dedication, null);
  assert.equal(checking.open, false);
  const reopened = dedicationReducer(checking, {
    type: "loaded",
    scope,
    requestId: 2,
    response: { dedication: letter, auto_open: false },
    manual: true,
  });
  assert.equal(reopened.open, true);
  assert.equal(reopened.dedication.id, letter.id);
});

test("confirmed session expiry clears the private text and cannot replay it", () => {
  const dismissed = dedicationReducer(loaded(), {
    type: "dismiss",
    scope,
    requestId: 1,
  });
  const expired = dedicationReducer(dismissed, {
    type: "expired",
    scope,
    requestId: 1,
  });
  assert.equal(expired.status, "expired");
  assert.equal(expired.dedication, null);
  assert.equal(expired.open, false);
  assert.equal(expired.saving, false);
  assert.equal(expired.dismissalError, "");
  assert.equal(dedicationBlocksTour(expired), true);
});

test("HTTP 401 from the API expires the letter, while HTTP 503 remains retryable", async () => {
  const originalFetch = globalThis.fetch;
  try {
    for (const status of [401, 503]) {
      globalThis.fetch = async () =>
        new Response(JSON.stringify({ detail: "Synthetischer Fehler" }), {
          status,
          headers: { "Content-Type": "application/json" },
        });
      for (const operation of ["load", "dismiss"]) {
        let failure;
        try {
          await api(
            "/dedication" + (operation === "dismiss" ? "/dismiss" : ""),
            operation === "dismiss" ? { id: 7, version: 2 } : undefined,
          );
        } catch (error) {
          failure = error;
        }
        assert.ok(failure instanceof ApiError);
        const type = dedicationFailureType(failure.status, operation);
        assert.equal(
          type,
          status === 401
            ? "expired"
            : operation === "load"
              ? "failed"
              : "dismiss-failed",
        );
        const next = dedicationReducer(loaded(), { type, scope, requestId: 1 });
        if (status === 401) {
          assert.equal(next.dedication, null);
          assert.equal(next.status, "expired");
          assert.equal(next.open, false);
        }
      }
    }
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test("a recipient without a letter sees no dialog and can take the tour", () => {
  const state = dedicationReducer(loading(), {
    type: "loaded",
    scope,
    requestId: 1,
    response: { dedication: null, auto_open: false },
    manual: false,
  });
  assert.equal(state.dedication, null);
  assert.equal(state.open, false);
  assert.equal(dedicationBlocksTour(state), false);
});

test("load errors are distinguishable from no letter, retry can open the message", () => {
  const failed = dedicationReducer(loading(), {
    type: "failed",
    scope,
    requestId: 1,
  });
  assert.equal(failed.status, "error");
  assert.ok(failed.loadError);
  assert.equal(dedicationBlocksTour(failed), false);
  const retry = dedicationReducer(failed, {
    type: "load",
    scope,
    requestId: 2,
  });
  const result = dedicationReducer(retry, {
    type: "loaded",
    scope,
    requestId: 2,
    response: { dedication: letter, auto_open: false },
    manual: true,
  });
  assert.equal(result.open, true);
  assert.equal(result.loadError, "");
});

test("a failed dismissal retains a retryable hint without trapping the user", () => {
  const dismissed = dedicationReducer(loaded(), {
    type: "dismiss",
    scope,
    requestId: 1,
  });
  const failed = dedicationReducer(dismissed, {
    type: "dismiss-failed",
    scope,
    requestId: 1,
  });
  assert.equal(failed.open, false);
  assert.equal(failed.saving, false);
  assert.ok(failed.dismissalError);
  assert.equal(failed.dedication.id, letter.id);
  assert.equal(dedicationBlocksTour(failed), false);
});

test("logout and account changes hide the previous account's text immediately", () => {
  const old = loaded();
  const signedOut = dedicationForScope(old, null);
  assert.equal(signedOut.dedication, null);
  assert.equal(signedOut.open, false);
  const other = dedicationForScope(old, "test-session-2");
  assert.equal(other.dedication, null);
  assert.equal(other.open, false);
  assert.equal(dedicationBlocksTour(other), true);
});

test("late requests from another session or StrictMode setup cannot overwrite the current state", () => {
  const current = loading("test-session-2", 3);
  for (const action of [
    {
      type: "loaded",
      scope,
      requestId: 1,
      response: { dedication: letter, auto_open: true },
      manual: false,
    },
    { type: "failed", scope: "test-session-2", requestId: 2 },
    { type: "dismissed", scope, requestId: 1 },
    { type: "dismiss-failed", scope, requestId: 1 },
  ])
    assert.equal(dedicationReducer(current, action), current);
});

test("an old dismissal cannot close a newer message or overwrite its state", () => {
  const replacement = dedicationReducer(loading(scope, 4), {
    type: "loaded",
    scope,
    requestId: 4,
    response: { dedication: { ...letter, version: 3 }, auto_open: true },
    manual: false,
  });
  assert.equal(
    dedicationReducer(replacement, { type: "dismissed", scope, requestId: 1 }),
    replacement,
  );
  assert.equal(replacement.open, true);
});

test("response validation rejects malformed data instead of silently treating it as no message", () => {
  assert.deepEqual(
    parseDedicationResponse({ dedication: letter, auto_open: true }),
    { dedication: letter, auto_open: true },
  );
  assert.deepEqual(
    parseDedicationResponse({ dedication: null, auto_open: false }),
    { dedication: null, auto_open: false },
  );
  for (const value of [
    null,
    {},
    { dedication: null },
    { dedication: null, auto_open: true },
    { dedication: { ...letter, id: 0 }, auto_open: true },
    { dedication: { ...letter, paragraphs: "wrong" }, auto_open: true },
  ])
    assert.throws(() => parseDedicationResponse(value), /Nachricht/);
});
