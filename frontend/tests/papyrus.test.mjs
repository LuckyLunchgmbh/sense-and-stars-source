import assert from "node:assert/strict";
import test from "node:test";
import { readFileSync } from "node:fs";
import vm from "node:vm";
import { traceGlyph } from "../src/papyrus/glyphTrace.ts";

function curvedStroke() {
  const width = 100,
    height = 120;
  const rgba = new Uint8ClampedArray(width * height * 4);
  for (let t = 0; t <= 1; t += 0.002) {
    const x = 50 + 27 * Math.sin((t * 2 - 1) * Math.PI),
      y = 16 + t * 88;
    for (let dy = -4; dy <= 4; dy++)
      for (let dx = -4; dx <= 4; dx++) {
        if (dx * dx + dy * dy <= 16)
          rgba[((Math.round(y) + dy) * width + Math.round(x) + dx) * 4 + 3] =
            255;
      }
  }
  return { rgba, width, height };
}

test("burning follows a connected S curve with both horizontal directions", () => {
  const { rgba, width, height } = curvedStroke();
  const result = traceGlyph(rgba, width, height);
  assert.equal(result.components, 1);
  assert.ok(result.points.length > 80);
  let left = false,
    right = false;
  for (let i = 1; i < result.points.length; i++) {
    const dx = result.points[i][0] - result.points[i - 1][0];
    left ||= dx < 0;
    right ||= dx > 0;
  }
  assert.ok(
    left && right,
    "stroke must turn back along the letter, not wipe horizontally",
  );
  assert.ok(result.pixels.some((v, i) => i % 4 === 0 && v > 200));
  assert.ok(result.pixels.some((v, i) => i % 4 === 0 && v > 0 && v < 50));
});

test("empty glyphs contain neither a stroke nor a fire mask", () => {
  const result = traceGlyph(new Uint8ClampedArray(32 * 32 * 4), 32, 32);
  assert.equal(result.components, 0);
  assert.deepEqual(result.points, []);
  assert.ok(result.pixels.every((v) => v === 0));
});

test("diagonal pen movement continues along its stem before a diverging branch", () => {
  const width = 100,
    height = 90,
    rgba = new Uint8ClampedArray(width * height * 4);
  for (let t = 0; t <= 60; t++) rgba[((10 + t) * width + 80 - t) * 4 + 3] = 255;
  for (let t = 0; t <= 30; t++) rgba[((40 + t) * width + 50 + t) * 4 + 3] = 255;
  const { points } = traceGlyph(rgba, width, height);
  const stem = points.findIndex(([x, y]) => x === 22 && y === 68);
  const branch = points.findIndex(([x, y]) => x === 78 && y === 68);
  assert.ok(stem >= 0 && branch >= 0);
  assert.ok(
    stem < branch,
    "continue downward-left instead of turning into the right branch",
  );
});

test("glyph processing keeps input immutable and does not retain an earlier letter", () => {
  const { rgba, width, height } = curvedStroke();
  const original = rgba.slice();
  const first = traceGlyph(rgba, width, height);
  assert.deepEqual(rgba, original);
  first.pixels.fill(0);
  const next = traceGlyph(rgba, width, height);
  assert.ok(next.pixels.some((v) => v > 0));
  assert.ok(
    traceGlyph(new Uint8ClampedArray(rgba.length), width, height).pixels.every(
      (v) => v === 0,
    ),
  );
});

function worker() {
  const handlers = new Map(),
    requested = [],
    cached = [];
  const scope = {
    URL,
    self: {
      location: { origin: "https://app.example" },
      addEventListener: (event, handler) => handlers.set(event, handler),
      skipWaiting() {},
      clients: { claim() {} },
    },
    fetch: async (request) => {
      requested.push(request.url);
      return { ok: true, type: "basic", clone: () => ({ public: true }) };
    },
    caches: {
      open: async () => ({ put: async (request) => cached.push(request.url) }),
    },
  };
  vm.runInNewContext(
    readFileSync(new URL("../public/sw.js", import.meta.url), "utf8"),
    scope,
  );
  return { handlers, requested, cached };
}

test("PWA never intercepts private API, writes, or another origin", () => {
  const { handlers, requested } = worker();
  for (const [url, method] of [
    ["https://app.example/api/dedication", "GET"],
    ["https://app.example/api/learning", "GET"],
    ["https://app.example/api/auth/login", "POST"],
    ["https://app.example/assets/paper.png", "POST"],
    ["https://external.example/assets/paper.png", "GET"],
  ]) {
    let intercepted = false;
    handlers.get("fetch")({
      request: { url, method },
      respondWith: () => {
        intercepted = true;
      },
    });
    assert.equal(intercepted, false, url);
  }
  assert.deepEqual(requested, []);
});

test("PWA may cache the public hashed paper texture", async () => {
  const { handlers, requested, cached } = worker();
  const url = "https://app.example/assets/paper-abcd1234.png";
  let response;
  handlers.get("fetch")({
    request: { url, method: "GET" },
    respondWith: (value) => {
      response = value;
    },
  });
  await response;
  assert.deepEqual(requested, [url]);
  assert.deepEqual(cached, [url]);
});
