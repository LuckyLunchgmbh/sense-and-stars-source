export type PapyrusArrival =
  "waiting" | "veiling" | "entering" | "ready" | "leaving";

export const PAPYRUS_MOTION = {
  prelude: 280,
  entrance: 1100,
  exit: 560,
} as const;

/** A short pause at punctuation keeps the faster pen readable. */
export function writingDuration(char: string) {
  return !char.trim()
    ? 9
    : /[.,…!?]/u.test(char)
      ? 75
      : /[A-ZÄÖÜ]/u.test(char)
        ? 82
        : 48;
}

interface TransitionOptions {
  stage: (value: PapyrusArrival) => void;
  presented: () => void;
  close: () => void;
  reduced: () => boolean;
  now?: () => number;
  after?: (ms: number, callback: () => void) => () => void;
}

/** Owns only the arrival/exit, so every opening follows the same choreography. */
export function createPapyrusTransition(options: TransitionOptions) {
  const now = options.now ?? (() => performance.now());
  const after =
    options.after ??
    ((ms, callback) => {
      const timer = window.setTimeout(callback, ms);
      return () => window.clearTimeout(timer);
    });
  const pending = new Set<() => void>();
  let active = true,
    began: number | null = null,
    assets = false;
  let stage: PapyrusArrival = "waiting",
    acknowledged = false;
  function change(value: PapyrusArrival) {
    stage = value;
    options.stage(value);
  }
  function cancel() {
    pending.forEach((stop) => stop());
    pending.clear();
  }
  function later(ms: number, callback: () => void) {
    const stop = after(ms, () => {
      pending.delete(stop);
      if (active) callback();
    });
    pending.add(stop);
  }
  function settled() {
    change("ready");
    if (!acknowledged) {
      acknowledged = true;
      options.presented();
    }
  }
  function reveal() {
    assets = true;
    if (!active || began === null || stage !== "veiling") return;
    cancel();
    if (options.reduced()) {
      settled();
      return;
    }
    later(Math.max(0, PAPYRUS_MOTION.prelude - (now() - began)), () => {
      change("entering");
      later(PAPYRUS_MOTION.entrance, settled);
    });
  }
  return {
    begin() {
      if (!active || began !== null || stage === "leaving") return;
      began = now();
      change("veiling");
      if (assets) reveal();
    },
    reveal,
    suspend() {
      if (!active || stage === "ready" || stage === "leaving") return;
      cancel();
      began = null;
      change("waiting");
    },
    preferencesChanged() {
      if (!active || !options.reduced()) return;
      if (stage === "leaving") {
        cancel();
        later(0, options.close);
      } else if (assets && began !== null && stage !== "ready") {
        cancel();
        settled();
      }
    },
    leave() {
      if (!active || stage === "leaving") return;
      cancel();
      change("leaving");
      later(options.reduced() ? 0 : PAPYRUS_MOTION.exit, options.close);
    },
    dispose() {
      active = false;
      cancel();
    },
  };
}
