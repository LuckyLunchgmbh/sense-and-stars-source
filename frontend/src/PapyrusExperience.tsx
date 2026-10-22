import { useEffect, useId, useRef, useState } from "react";
import type { Dedication } from "./dedicationState";
import type {
  LetterBlock,
  PapyrusPhase,
  PapyrusRenderer,
} from "./papyrus/renderer";
import paperUrl from "./papyrus/paper.png";
import "./PapyrusExperience.css";

export function PapyrusExperience({
  letter,
  onClose,
}: {
  letter: Dedication;
  onClose: () => void;
}) {
  const dialog = useRef<HTMLDialogElement>(null);
  const scene = useRef<HTMLCanvasElement>(null);
  const scroller = useRef<HTMLDivElement>(null);
  const scrollSpace = useRef<HTMLDivElement>(null);
  const seal = useRef<HTMLButtonElement>(null);
  const reader = useRef<HTMLDivElement>(null);
  const renderer = useRef<PapyrusRenderer | null>(null);
  const plainRef = useRef(false);
  const reducedRef = useRef(false);
  const loadTimerRef = useRef<number | undefined>(undefined);
  const close = useRef(onClose);
  close.current = onClose;
  const titleId = useId();
  const [phase, setPhase] = useState<PapyrusPhase>("loading");
  const [reduced, setReduced] = useState(false);
  const [plain, setPlain] = useState(false);
  const [atEnd, setAtEnd] = useState(false);
  const [status, setStatus] = useState("Die Papyrusrolle wird vorbereitet.");
  plainRef.current = plain;

  useEffect(() => {
    const node = dialog.current;
    const canvas = scene.current;
    const input = scroller.current;
    const space = scrollSpace.current;
    const sealButton = seal.current;
    if (!node || !canvas || !input || !space || !sealButton) return;
    let active = true;
    let ready = false;
    let suspended = !navigator.onLine;
    const previous = document.activeElement as HTMLElement | null;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    const preference = matchMedia("(prefers-reduced-motion: reduce)");
    reducedRef.current = preference.matches;
    setReduced(preference.matches);
    setPhase("loading");
    setAtEnd(false);
    setPlain(false);
    plainRef.current = false;
    const showPlain = () => {
      if (!active) return;
      plainRef.current = true;
      clearTimeout(loadTimerRef.current);
      renderer.current?.dispose();
      renderer.current = null;
      setPlain(true);
      setStatus("Dein Brief ist ohne räumliche Effekte lesbar.");
    };
    const changePreference = (event: MediaQueryListEvent) => {
      if (!active) return;
      reducedRef.current = event.matches;
      setReduced(event.matches);
      renderer.current?.setReduced(event.matches);
    };
    const suspend = () => {
      suspended = node.open;
      node.close();
      document.body.style.overflow = previousOverflow;
    };
    const resume = () => {
      if (active && suspended && node.isConnected && !node.open) {
        node.showModal();
        document.body.style.overflow = "hidden";
      }
      suspended = false;
    };
    if (!suspended) node.showModal();
    node.focus({ preventScroll: true });
    preference.addEventListener("change", changePreference);
    window.addEventListener("offline", suspend);
    window.addEventListener("online", resume);
    const loadTimer = window.setTimeout(() => {
      if (!ready) showPlain();
    }, 15000);
    loadTimerRef.current = loadTimer;
    const source: LetterBlock[] = [
      { text: letter.title, kind: "title" },
      { text: letter.salutation, kind: "salutation" },
      ...letter.paragraphs.map((text) => ({ text, kind: "body" as const })),
      { text: letter.closing, kind: "body" },
      { text: letter.sender, kind: "sender" },
    ];
    // The heavy renderer is fetched only after an authorized letter is mounted.
    void import("./papyrus/renderer")
      .then(({ createPapyrusRenderer }) => {
        if (!active || plainRef.current) return;
        renderer.current = createPapyrusRenderer({
          elements: {
            dialog: node,
            canvas,
            scroller: input,
            scrollSpace: space,
            seal: sealButton,
          },
          source,
          paperUrl,
          reduced: reducedRef.current,
          onPhase: (value) => active && setPhase(value),
          onStatus: (value) => active && setStatus(value),
          onEnd: (value) => active && setAtEnd(value),
          onReady: () => {
            ready = true;
            clearTimeout(loadTimer);
            if (active && !suspended) sealButton.focus({ preventScroll: true });
          },
          onFailure: showPlain,
        });
      })
      .catch(showPlain);
    return () => {
      active = false;
      clearTimeout(loadTimer);
      renderer.current?.dispose();
      renderer.current = null;
      source.length = 0;
      preference.removeEventListener("change", changePreference);
      window.removeEventListener("offline", suspend);
      window.removeEventListener("online", resume);
      node.close();
      document.body.style.overflow = previousOverflow;
      if (previous?.isConnected && previous !== document.body)
        previous.focus({ preventScroll: true });
      else
        document.getElementById("main-content")?.focus({ preventScroll: true });
    };
  }, [letter]);

  useEffect(() => {
    if (plain) reader.current?.focus({ preventScroll: true });
  }, [plain]);

  function plainRead() {
    plainRef.current = true;
    clearTimeout(loadTimerRef.current);
    renderer.current?.dispose();
    renderer.current = null;
    setPlain(true);
    setStatus("Dein Brief ist ohne räumliche Effekte lesbar.");
  }
  const opened = phase === "writing" || phase === "reading";
  return (
    <dialog
      ref={dialog}
      className={`dedication-modal papyrus-experience${reduced ? " papyrus-motion-off" : ""}${plain ? " papyrus-plain" : ""}`}
      aria-label="Ein persönlicher Brief für dich"
      closedby="none"
      tabIndex={-1}
      data-phase={phase}
      onCancel={(event) => event.preventDefault()}
      onKeyDown={(event) => {
        if (event.key === "Escape") {
          event.preventDefault();
          event.stopPropagation();
        }
      }}
    >
      <div className="papyrus-veil" />
      <canvas ref={scene} className="papyrus-scene" aria-hidden="true" />
      {!plain && (
        <>
          <div
            className="papyrus-intro"
            aria-hidden={phase !== "sealed" && phase !== "loading"}
          >
            <h1>für dich</h1>
            <p>Ein persönlicher Brief für dich.</p>
          </div>
          <button
            ref={seal}
            className="papyrus-seal"
            aria-label="Unendlichkeitssiegel berühren und die Papyrusrolle öffnen"
            disabled={phase !== "sealed"}
            onClick={() => renderer.current?.open()}
          />
          <p className="papyrus-invitation">
            {phase === "loading"
              ? "Deine Rolle wird vorbereitet …"
              : "Berühre das Unendlichkeitssiegel."}
          </p>
        </>
      )}
      <div
        ref={scroller}
        className="papyrus-scroller"
        tabIndex={opened && !plain ? 0 : -1}
        aria-hidden={!opened || plain}
        role="region"
        aria-label="Papyrusbrief. Mit Mausrad, Wischgeste oder Pfeiltasten weiter entrollen."
      >
        <div ref={scrollSpace} className="papyrus-scroll-space" />
      </div>
      <div
        ref={reader}
        className={plain ? "papyrus-reader" : "papyrus-semantic"}
        aria-hidden={!plain && !opened}
        tabIndex={plain ? -1 : undefined}
        role={plain ? "document" : undefined}
        aria-labelledby={plain ? titleId : undefined}
      >
        <article>
          <h2 id={titleId}>{letter.title}</h2>
          <div className="papyrus-reader-ornament" aria-hidden="true">
            <span />∞<span />
          </div>
          <p className="papyrus-salutation">{letter.salutation}</p>
          {letter.paragraphs.map((paragraph, index) => (
            <p key={index}>{paragraph}</p>
          ))}
          <p className="papyrus-closing">
            {letter.closing}
            <span>{letter.sender}</span>
          </p>
          {plain && (
            <button
              className="papyrus-reader-finish"
              onClick={() => close.current()}
            >
              In meinen Raum <span aria-hidden="true">↗</span>
            </button>
          )}
        </article>
      </div>
      {!plain && (
        <>
          <div className="papyrus-controls">
            {phase !== "loading" && phase !== "sealed" && (
              <button
                onClick={() => {
                  setAtEnd(false);
                  renderer.current?.reset();
                  seal.current?.focus({ preventScroll: true });
                }}
              >
                Noch einmal erleben
              </button>
            )}
            {(phase === "opening" || phase === "writing") && (
              <button onClick={() => renderer.current?.showAll()}>
                Schrift vollständig zeigen
              </button>
            )}
            <label>
              <input
                type="checkbox"
                checked={reduced}
                onChange={(event) => {
                  reducedRef.current = event.target.checked;
                  setReduced(event.target.checked);
                  renderer.current?.setReduced(event.target.checked);
                }}
              />{" "}
              Ohne Effekte
            </label>
            <button onClick={plainRead}>Einfach lesen</button>
          </div>
          {opened && !atEnd && (
            <p className="papyrus-reading-cue" aria-hidden="true">
              Entrolle deine Worte beim Weiterlesen <span>↓</span>
            </p>
          )}
          {opened && atEnd && (
            <button className="papyrus-finish" onClick={() => close.current()}>
              In meinen Raum <span aria-hidden="true">↗</span>
            </button>
          )}
        </>
      )}
      <p className="papyrus-semantic" role="status">
        {status}
      </p>
    </dialog>
  );
}
