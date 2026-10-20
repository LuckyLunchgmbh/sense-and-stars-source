import assert from "node:assert/strict";
import test from "node:test";
import { localDateTime, toBerlinISO } from "../src/api.ts";

test("Berlin appointments do not shift with the device timezone", () => {
  const previous = process.env.TZ;
  try {
    for (const zone of ["UTC", "America/New_York", "Asia/Tokyo"]) {
      process.env.TZ = zone;
      assert.equal(toBerlinISO("2026-10-21T10:00"), "2026-10-21T08:00:00.000Z");
      assert.equal(toBerlinISO("2026-12-21T10:00"), "2026-12-21T09:00:00.000Z");
      assert.equal(localDateTime("2026-12-21T09:00:00Z"), "2026-12-21T10:00");
    }
  } finally {
    if (previous === undefined) delete process.env.TZ;
    else process.env.TZ = previous;
  }
});

test("nonexistent Berlin daylight-saving time is never guessed", () => {
  assert.throws(() => toBerlinISO("2026-03-29T02:30"), /existiert/);
});

test("ambiguous Berlin daylight-saving time is never guessed", () => {
  assert.throws(() => toBerlinISO("2026-10-25T02:30"), /zweimal/);
});
