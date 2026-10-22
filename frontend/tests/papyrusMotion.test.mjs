import assert from "node:assert/strict";
import test from "node:test";
import {
  createPapyrusTransition,
  writingDuration,
} from "../src/papyrus/motion.ts";

function rig(reduced = false) {
  let now = 0,
    serial = 0,
    shown = 0,
    closed = 0;
  const pending = new Map(),
    stages = [];
  const transition = createPapyrusTransition({
    stage: (value) => stages.push(value),
    presented: () => shown++,
    close: () => closed++,
    reduced: () => reduced,
    now: () => now,
    after: (ms, callback) => {
      const id = ++serial;
      pending.set(id, { at: now + ms, callback });
      return () => pending.delete(id);
    },
  });
  function advance(ms) {
    const end = now + ms;
    while (true) {
      const next = [...pending.entries()]
        .filter(([, job]) => job.at <= end)
        .sort((a, b) => a[1].at - b[1].at)[0];
      if (!next) break;
      now = next[1].at;
      pending.delete(next[0]);
      next[1].callback();
    }
    now = end;
  }
  return {
    transition,
    stages,
    advance,
    reduced: (value) => {
      reduced = value;
      transition.preferencesChanged();
    },
    get shown() {
      return shown;
    },
    get closed() {
      return closed;
    },
    get pending() {
      return pending.size;
    },
  };
}

test("entrance darkens first and acknowledges only after the roll has arrived", () => {
  const r = rig();
  r.transition.reveal();
  assert.deepEqual(r.stages, []); // Assets may finish before the first painted dialog.
  r.transition.begin();
  assert.deepEqual(r.stages, ["veiling"]);
  r.advance(200);
  assert.equal(r.shown, 0);
  assert.equal(r.stages.at(-1), "veiling");
  r.advance(200);
  assert.equal(r.stages.at(-1), "entering");
  assert.equal(r.shown, 0);
  r.advance(1300);
  assert.equal(r.stages.at(-1), "ready");
  assert.equal(r.shown, 1);
  r.transition.reveal();
  r.advance(2000);
  assert.equal(r.shown, 1);
});

test("late assets stay hidden until ready, then use the same entrance", () => {
  const r = rig();
  r.transition.begin();
  r.advance(3000);
  assert.deepEqual(r.stages, ["veiling"]);
  assert.equal(r.shown, 0);
  r.transition.reveal();
  r.advance(0);
  assert.equal(r.stages.at(-1), "entering");
  r.advance(1300);
  assert.equal(r.stages.at(-1), "ready");
  assert.equal(r.shown, 1);
});

test("exit keeps the modal mounted until its fade is complete and only closes once", () => {
  const r = rig();
  r.transition.begin();
  r.transition.reveal();
  r.advance(2000);
  r.transition.leave();
  r.transition.leave();
  assert.equal(r.stages.at(-1), "leaving");
  assert.equal(r.closed, 0);
  r.advance(200);
  assert.equal(r.closed, 0);
  r.advance(1000);
  assert.equal(r.closed, 1);
});

test("unmount cancels entry and exit work, never acknowledging another account", () => {
  for (const exit of [false, true]) {
    const r = rig();
    r.transition.begin();
    r.transition.reveal();
    if (exit) r.transition.leave();
    r.transition.dispose();
    r.advance(10000);
    assert.equal(r.shown, 0);
    assert.equal(r.closed, 0);
    assert.equal(r.pending, 0);
  }
});

test("reduced motion selected during loading settles as soon as assets arrive", () => {
  const r = rig();
  r.transition.begin();
  r.reduced(true);
  r.transition.reveal();
  r.advance(0);
  assert.equal(r.stages.at(-1), "ready");
  assert.equal(r.shown, 1);
  r.transition.leave();
  r.advance(0);
  assert.equal(r.closed, 1);
});

test("reducing during entrance cancels the pending delayed acknowledgement", () => {
  const r = rig();
  r.transition.begin();
  r.transition.reveal();
  r.advance(400);
  r.reduced(true);
  r.advance(0);
  assert.equal(r.stages.at(-1), "ready");
  assert.equal(r.shown, 1);
  r.advance(3000);
  assert.equal(r.shown, 1);
});

test("writing a reading-sized paragraph takes under twelve seconds and retains punctuation rhythm", () => {
  const paragraph =
    "Manche Begegnungen bleiben. Ein neuer Weg beginnt mit einem kleinen Schritt. Hier darfst du neugierig sein und Neues entdecken. Nimm dir die Zeit, die du brauchst, und folge deinem eigenen Tempo.";
  const duration = [...paragraph].reduce(
    (sum, char) => sum + writingDuration(char),
    0,
  );
  assert.ok(duration < 12000, `${duration}ms blocks comfortable reading`);
  assert.ok(writingDuration(" ") < writingDuration("e"));
  assert.ok(writingDuration(".") > writingDuration("e"));
  assert.ok(writingDuration("S") > writingDuration("s"));
});

test("a hidden or offline entrance pauses without receipt and restarts its soft arrival", () => {
  const r = rig();
  r.transition.begin();
  r.transition.reveal();
  r.advance(500);
  r.transition.suspend();
  r.advance(5000);
  assert.equal(r.shown, 0);
  assert.equal(r.stages.at(-1), "waiting");
  r.transition.begin();
  r.advance(200);
  assert.equal(r.stages.at(-1), "veiling");
  assert.equal(r.shown, 0);
  r.advance(1500);
  assert.equal(r.stages.at(-1), "ready");
  assert.equal(r.shown, 1);
});
