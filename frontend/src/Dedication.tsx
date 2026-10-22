import { Icon } from "./ui";
import { PapyrusExperience } from "./PapyrusExperience";
import type { Dedication } from "./dedicationState";
import type { DedicationController } from "./useDedication";

export function InfinityMark({ className = "" }: { className?: string }) {
  return (
    <svg
      className={className}
      viewBox="0 0 80 34"
      fill="none"
      aria-hidden="true"
      focusable="false"
    >
      <path
        d="M40 17C32 7 26 4 19 4a13 13 0 0 0 0 26c8 0 14-5 21-13S53 4 61 4a13 13 0 0 1 0 26c-7 0-13-3-21-13Z"
        stroke="currentColor"
        strokeWidth="1.7"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

export function DedicationDialog({
  letter,
  onClose,
}: {
  letter: Dedication;
  onClose: () => void;
}) {
  return (
    <PapyrusExperience
      key={`${letter.id}:${letter.version}`}
      letter={letter}
      onClose={onClose}
    />
  );
}

export function DedicationNotice({
  controller,
}: {
  controller: DedicationController;
}) {
  const { state, retry, dismiss } = controller;
  const error = state.loadError || state.dismissalError;
  if (!error) return null;
  return (
    <div className="dedication-notice" role="status">
      <Icon name="note" size={19} />
      <p>{error}</p>
      <button
        className="button secondary small"
        disabled={state.saving}
        onClick={() => (state.loadError ? retry() : void dismiss())}
      >
        {state.loadError
          ? "Erneut laden"
          : state.saving
            ? "Wird gespeichert …"
            : "Schließen erneut speichern"}
      </button>
    </div>
  );
}

export function DedicationSettings({
  controller,
}: {
  controller: DedicationController;
}) {
  const { state, open, retry } = controller;
  if (state.status === "ready" && !state.dedication) return null;
  return (
    <section className="glass-card settings-card dedication-settings">
      <span className="card-icon crown">
        <Icon name="note" />
      </span>
      <h2>Deine persönliche Nachricht.</h2>
      {state.status === "loading" ? (
        <p role="status">Deine Nachricht wird geladen …</p>
      ) : state.loadError ? (
        <>
          <p>{state.loadError}</p>
          <button className="button secondary" onClick={retry}>
            Erneut laden <Icon name="arrow" size={17} />
          </button>
        </>
      ) : (
        <>
          <p>
            Die Worte, die dir mit auf den Weg gegeben wurden. Hier kannst du
            sie jederzeit in Ruhe noch einmal lesen.
          </p>
          <button className="button secondary" onClick={open}>
            Nachricht noch einmal lesen <Icon name="arrow" size={17} />
          </button>
        </>
      )}
    </section>
  );
}
