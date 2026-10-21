import assert from "node:assert/strict";
import test from "node:test";
import {
  captureRecoveryLink,
  parseRecoveryLink,
  recoveryRequestError,
  validateRecoveryPassword,
} from "../src/recoveryLink.ts";

const syntheticToken = "synthetic-reset-token-only-for-testing_1234";

test("reset link captures a URL-safe token from its fragment", () => {
  assert.equal(syntheticToken.length, 43);
  assert.deepEqual(
    parseRecoveryLink(`#reset-password?token=${syntheticToken}`),
    {
      token: syntheticToken,
    },
  );
});

test("token length matches the backend's exact 43-character format", () => {
  for (const length of [40, 42, 44, 256]) {
    assert.deepEqual(
      parseRecoveryLink(`#reset-password?token=${"a".repeat(length)}`),
      { token: null },
    );
  }
});

test("a temporarily unavailable request never claims missing configuration or unsent mail", () => {
  const message = recoveryRequestError(503);
  assert.match(message, /vorübergehend nicht verfügbar/);
  assert.match(message, /nicht zuverlässig bestätigt/);
  assert.match(message, /E-Mail-Postfach/);
  assert.doesNotMatch(
    message,
    /nicht eingerichtet|keine E-Mail|wurde.*verschickt|wurde.*gesendet/,
  );
});

test("ordinary and practice routes are not reset routes", () => {
  for (const hash of [
    "",
    "#home",
    "#practice/learning",
    "#forgot-password",
    "#practice/reset-password?token=ignored",
  ])
    assert.equal(parseRecoveryLink(hash), null);
});

test("missing, malformed and ambiguous tokens fail closed without echoing them", () => {
  for (const hash of [
    "#reset-password",
    "#reset-password?token=",
    "#reset-password?token=short",
    `#reset-password?token=${syntheticToken}&token=${syntheticToken}`,
    `#reset-password?token=${syntheticToken}%20`,
    `#reset-password?token=${"a".repeat(257)}`,
  ])
    assert.deepEqual(parseRecoveryLink(hash), { token: null });
});

test("capture replaces the URL synchronously and preserves unrelated path, query and history state", () => {
  const state = { app: "synthetic-navigation" };
  const replacements = [];
  const link = captureRecoveryLink(
    {
      pathname: "/",
      search: "?display=compact",
      hash: `#reset-password?token=${syntheticToken}`,
    },
    { state, replaceState: (...args) => replacements.push(args) },
  );
  assert.deepEqual(link, { token: syntheticToken });
  assert.deepEqual(replacements, [
    [state, "", "/?display=compact#reset-password"],
  ]);
  assert.ok(!JSON.stringify(replacements).includes(syntheticToken));
});

test("capture also removes malformed token data and leaves ordinary navigation alone", () => {
  const replacements = [];
  const history = {
    state: null,
    replaceState: (...args) => replacements.push(args),
  };
  assert.deepEqual(
    captureRecoveryLink(
      {
        pathname: "/app",
        search: "",
        hash: "#reset-password?token=bad&extra=remove",
      },
      history,
    ),
    { token: null },
  );
  assert.deepEqual(replacements, [[null, "", "/app#reset-password"]]);
  replacements.length = 0;
  assert.equal(
    captureRecoveryLink(
      { pathname: "/", search: "", hash: "#learning" },
      history,
    ),
    null,
  );
  assert.equal(replacements.length, 0);
});

test("after reload the cleaned URL has no reusable token", () => {
  const location = {
    pathname: "/",
    search: "",
    hash: `#reset-password?token=${syntheticToken}`,
  };
  const history = {
    state: null,
    replaceState: (_state, _unused, url) => {
      location.hash = new URL(url, "https://example.invalid").hash;
    },
  };
  const captured = captureRecoveryLink(location, history);
  assert.equal(captured.token, syntheticToken);
  assert.deepEqual(captureRecoveryLink(location, history), { token: null });
  assert.equal(
    captured.token,
    syntheticToken,
    "the original in-memory value survives repeated rendering",
  );
});

test("password length matches server Unicode code-point boundaries", () => {
  assert.equal(validateRecoveryPassword("a".repeat(12), "a".repeat(12)), null);
  assert.equal(
    validateRecoveryPassword("a".repeat(256), "a".repeat(256)),
    null,
  );
  assert.equal(
    validateRecoveryPassword("🌟".repeat(12), "🌟".repeat(12)),
    null,
  );
  assert.equal(
    validateRecoveryPassword("🌟".repeat(256), "🌟".repeat(256)),
    null,
  );
  assert.match(
    validateRecoveryPassword("🌟".repeat(6), "🌟".repeat(6)),
    /12 bis 256/,
  );
  assert.match(
    validateRecoveryPassword("a".repeat(257), "a".repeat(257)),
    /12 bis 256/,
  );
});

test("confirmation must match exactly and feedback never contains either password", () => {
  const password = "Synthetic Three Words";
  const mismatch = "different private example";
  const feedback = validateRecoveryPassword(password, mismatch);
  assert.match(feedback, /stimmen noch nicht überein/);
  assert.ok(!feedback.includes(password));
  assert.ok(!feedback.includes(mismatch));
  assert.equal(validateRecoveryPassword(password, password), null);
  assert.notEqual(validateRecoveryPassword(password, ` ${password}`), null);
});
