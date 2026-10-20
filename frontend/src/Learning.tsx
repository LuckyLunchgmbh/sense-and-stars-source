import { useLayoutEffect, useRef, useState, type FormEvent } from "react";
import { api, dateFormat } from "./api";
import { useData } from "./hooks";
import type {
  AdminLesson,
  LearningData,
  Lesson,
  NotebookNote,
  LearningUpdatesStatus,
  LearningUpdateResult,
  LearningUpdateSource,
} from "./types";
import { ContextHelp } from "./Help";
import type { PageProps } from "./App";
import {
  Badge,
  Empty,
  ErrorBox,
  Icon,
  Loading,
  Modal,
  SectionTitle,
} from "./ui";

type WorkspaceTab = "library" | "bookmarks" | "pins" | "notebook" | "sources";
type LessonState = "bookmarked" | "pinned" | "practiced" | "reflected";
const LEVELS: Record<string, string> = {
  foundation: "Grundlagen",
  deepening: "Vertiefung",
  practice: "Praxis",
};
const TABS: { id: WorkspaceTab; label: string }[] = [
  { id: "library", label: "Bibliothek" },
  { id: "bookmarks", label: "Lesezeichen" },
  { id: "pins", label: "Pinnwand" },
  { id: "notebook", label: "Notizbuch" },
  { id: "sources", label: "Quellen" },
];
function isSourceDraft(lesson: Lesson): boolean {
  return (
    lesson.source_kind === "simulation_metadata" ||
    lesson.source_kind === "rss_metadata" ||
    lesson.source_kind === "source_reading_draft"
  );
}
function LessonSource({ lesson }: { lesson: Lesson }) {
  return (
    <div className="source-box workspace-source-box">
      <Icon name="book" size={18} />
      <div>
        <strong>
          Quelle & Einordnung · Inhaltsversion {lesson.content_version || 1}
        </strong>
        {/^https?:\/\//.test(lesson.source_url) ? (
          <a href={lesson.source_url} target="_blank" rel="noopener noreferrer">
            {lesson.source_title || lesson.source_url}
            <Icon name="arrow" size={14} />
          </a>
        ) : (
          <span>
            {lesson.source_title || "Eigenständiger SoulFlow-Lehrtext"}
          </span>
        )}
        {lesson.source_note && <p>{lesson.source_note}</p>}
      </div>
    </div>
  );
}

export function LearningPage(props: PageProps) {
  const { data, setData, loading, error } = useData<LearningData>(
    "/learning",
    props.revision,
  );
  const [tab, setTab] = useState<WorkspaceTab>("library");
  const [selected, setSelected] = useState<Lesson | null>(null);
  const [editor, setEditor] = useState<{
    note?: NotebookNote;
    lesson?: Lesson;
  } | null>(null);
  const [query, setQuery] = useState("");
  const [track, setTrack] = useState("");
  const [level, setLevel] = useState("");
  const [pending, setPending] = useState<number | null>(null);
  const [actionError, setActionError] = useState("");
  const [saved, setSaved] = useState("");
  const notebook = useData<NotebookNote[]>(
    tab === "notebook" ? "/learning/notebook" : null,
    props.revision,
  );

  function lessonUpdated(lesson: Lesson) {
    setData((current) =>
      current
        ? {
            ...current,
            lessons: current.lessons.map((item) =>
              item.id === lesson.id ? lesson : item,
            ),
          }
        : current,
    );
    props.refresh();
  }
  async function toggle(lesson: Lesson, field: LessonState) {
    setPending(lesson.id);
    setActionError("");
    setSaved("");
    try {
      const updated = await api<Lesson>(
        `/learning/${lesson.id}/state`,
        { [field]: !lesson[field] },
        "PATCH",
      );
      lessonUpdated(updated);
      setSaved(
        field === "bookmarked"
          ? updated.bookmarked
            ? "Lesezeichen gespeichert."
            : "Lesezeichen entfernt."
          : updated.pinned
            ? "Auf deiner Pinnwand gespeichert."
            : "Von der Pinnwand genommen.",
      );
    } catch (e) {
      setActionError((e as Error).message);
    } finally {
      setPending(null);
    }
  }
  function createNote(lesson?: Lesson) {
    setSelected(null);
    setTab("notebook");
    setEditor({ lesson });
  }
  if (loading && !data) return <Loading />;
  if (!data) return <ErrorBox error={error} />;
  const lessons = data.lessons.filter(
    (lesson) => lesson.status === "published",
  );
  const tracks = [
    ...new Set(lessons.map((lesson) => lesson.track || lesson.category)),
  ];
  const recommended =
    lessons.find(
      (lesson) => lesson.level === "foundation" && !lesson.completed,
    ) ||
    lessons.find((lesson) => !lesson.completed) ||
    lessons[0];
  const completed = lessons.filter((lesson) => lesson.completed).length;
  const visible = lessons.filter((lesson) => {
    const inTab =
      tab === "bookmarks"
        ? lesson.bookmarked
        : tab === "pins"
          ? lesson.pinned
          : true;
    const search = [
      lesson.title,
      lesson.summary,
      lesson.track,
      lesson.category,
      lesson.learning_objective,
    ]
      .join(" ")
      .toLocaleLowerCase("de");
    return (
      inTab &&
      (!track || (lesson.track || lesson.category) === track) &&
      (!level || (lesson.level || "foundation") === level) &&
      search.includes(query.trim().toLocaleLowerCase("de"))
    );
  });
  const isLibrary = tab === "library" || tab === "bookmarks" || tab === "pins";
  return (
    <div className="learning-workspace" data-tour="learning">
      <div className="page-heading">
        <div>
          <span className="eyebrow">DEIN LERN- UND ARBEITSRAUM</span>
          <h1>
            Dein Weg. Deine Entdeckungen. <ContextHelp topic="learning" />
          </h1>
          <p>
            Astrologie, Intuition und achtsame Feldarbeit – wähle selbst, wo du
            beginnst.
          </p>
        </div>
        <span className="card-icon crown">
          <Icon name="book" size={24} />
        </span>
      </div>
      <section
        className="glass-card workspace-welcome"
        aria-label="Orientierung im Lernraum"
      >
        <div>
          <span className="eyebrow">OFFEN FÜR DEINEN EIGENEN RHYTHMUS</span>
          <h2>
            Ein Kapitel lesen.
            <br />
            <em>Etwas Eigenes daraus machen.</em>
          </h2>
          <p>
            Alle {lessons.length} veröffentlichten Kapitel sind offen. Merke dir
            Gedanken, übe in deinem Tempo und halte deine Erfahrungen im
            privaten Notizbuch fest.
          </p>
          <div className="workspace-overview">
            <span>
              <strong>{completed}</strong> gelesen
            </span>
            <span>
              <strong>{lessons.filter((l) => l.practiced).length}</strong> geübt
            </span>
            <span>
              <strong>{lessons.filter((l) => l.reflected).length}</strong>{" "}
              reflektiert
            </span>
          </div>
        </div>
        {recommended && (
          <div className="workspace-suggestion">
            <span className="small-label">EIN MÖGLICHER EINSTIEG</span>
            <h3>{recommended.title}</h3>
            <p>{recommended.summary}</p>
            <button
              className="button secondary"
              onClick={() => setSelected(recommended)}
            >
              Kapitel öffnen <Icon name="arrow" size={17} />
            </button>
            <small>
              Eine Einladung. Du kannst jedes andere Kapitel wählen.
            </small>
          </div>
        )}
      </section>
      <nav className="workspace-tabs" aria-label="Bereiche im Lernraum">
        {TABS.map((item) => (
          <button
            key={item.id}
            aria-current={tab === item.id ? "page" : undefined}
            className={tab === item.id ? "active" : ""}
            onClick={() => {
              setTab(item.id);
              setActionError("");
              setSaved("");
            }}
          >
            {item.label}
            {item.id === "bookmarks" && (
              <span>{lessons.filter((l) => l.bookmarked).length}</span>
            )}
            {item.id === "pins" && (
              <span>{lessons.filter((l) => l.pinned).length}</span>
            )}
          </button>
        ))}
      </nav>
      <ErrorBox error={error || actionError} />
      {saved && (
        <p className="workspace-feedback" role="status">
          <Icon name="check" size={16} />
          {saved}
        </p>
      )}
      {isLibrary && (
        <section aria-label={TABS.find((item) => item.id === tab)?.label}>
          <div className="workspace-section-heading">
            <div>
              <h2>
                {tab === "library"
                  ? "Was möchtest du entdecken?"
                  : tab === "bookmarks"
                    ? "Für einen späteren Moment."
                    : "Deine wichtigen Begleiter."}
              </h2>
              <p>
                {tab === "library"
                  ? "Grundlagen und Vertiefung stehen gleichberechtigt nebeneinander."
                  : tab === "bookmarks"
                    ? "Hier findest du die Kapitel, die du dir gemerkt hast."
                    : "Halte hilfreiche Kapitel griffbereit für deine eigene Praxis."}
              </p>
            </div>
          </div>
          <div className="workspace-filters">
            <label className="workspace-search">
              Kapitel suchen
              <div>
                <Icon name="search" size={18} />
                <input
                  type="search"
                  placeholder="Thema, Titel oder Lernziel"
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                />
              </div>
            </label>
            <label>
              Themenraum
              <select value={track} onChange={(e) => setTrack(e.target.value)}>
                <option value="">Alle Themen</option>
                {tracks.map((value) => (
                  <option key={value}>{value}</option>
                ))}
              </select>
            </label>
            <label>
              Niveau
              <select value={level} onChange={(e) => setLevel(e.target.value)}>
                <option value="">Alle Niveaus</option>
                {Object.entries(LEVELS).map(([value, label]) => (
                  <option key={value} value={value}>
                    {label}
                  </option>
                ))}
              </select>
            </label>
          </div>
          <div className="workspace-result-count" role="status">
            {visible.length} Kapitel
            {query || track || level ? " für deine Auswahl" : " zum Entdecken"}
            {(query || track || level) && (
              <button
                className="text-link"
                onClick={() => {
                  setQuery("");
                  setTrack("");
                  setLevel("");
                }}
              >
                Filter zurücksetzen
              </button>
            )}
          </div>
          {visible.length ? (
            <div className="workspace-lesson-grid">
              {visible.map((lesson) => (
                <article
                  className="glass-card workspace-lesson"
                  key={lesson.id}
                >
                  <div className="workspace-lesson-meta">
                    <span>{lesson.track || lesson.category}</span>
                    <Badge
                      tone={lesson.level === "deepening" ? "purple" : "neutral"}
                    >
                      {LEVELS[lesson.level] || "Grundlagen"}
                    </Badge>
                  </div>
                  <h3>
                    <button onClick={() => setSelected(lesson)}>
                      {lesson.title}
                    </button>
                  </h3>
                  <p>{lesson.summary}</p>
                  {lesson.learning_objective && (
                    <div className="workspace-objective">
                      <span>LERNZIEL</span>
                      {lesson.learning_objective}
                    </div>
                  )}
                  <div
                    className="workspace-marks"
                    aria-label="Deine Lernschritte"
                  >
                    <span className={lesson.completed ? "done" : ""}>
                      <Icon
                        name={lesson.completed ? "check" : "book"}
                        size={14}
                      />
                      Gelesen
                    </span>
                    <span className={lesson.practiced ? "done" : ""}>
                      <Icon
                        name={lesson.practiced ? "check" : "leaf"}
                        size={14}
                      />
                      Geübt
                    </span>
                    <span className={lesson.reflected ? "done" : ""}>
                      <Icon
                        name={lesson.reflected ? "check" : "note"}
                        size={14}
                      />
                      Reflektiert
                    </span>
                  </div>
                  <div className="workspace-card-actions">
                    <button
                      className="text-link"
                      onClick={() => setSelected(lesson)}
                    >
                      Lesen <Icon name="arrow" size={16} />
                    </button>
                    <div>
                      <button
                        className={
                          "workspace-action " +
                          (lesson.bookmarked ? "active" : "")
                        }
                        aria-pressed={Boolean(lesson.bookmarked)}
                        aria-label={`${lesson.title}: ${lesson.bookmarked ? "Lesezeichen entfernen" : "merken"}`}
                        disabled={pending !== null}
                        onClick={() => void toggle(lesson, "bookmarked")}
                      >
                        <Icon name="heart" size={17} />
                        <span>{lesson.bookmarked ? "Gemerkt" : "Merken"}</span>
                      </button>
                      <button
                        className={
                          "workspace-action " + (lesson.pinned ? "active" : "")
                        }
                        aria-pressed={Boolean(lesson.pinned)}
                        aria-label={`${lesson.title}: ${lesson.pinned ? "Pin entfernen" : "pinnen"}`}
                        disabled={pending !== null}
                        onClick={() => void toggle(lesson, "pinned")}
                      >
                        <Icon name="task" size={17} />
                        <span>{lesson.pinned ? "Gepinnt" : "Pinnen"}</span>
                      </button>
                    </div>
                  </div>
                </article>
              ))}
            </div>
          ) : (
            <Empty
              icon={tab === "pins" ? "task" : "book"}
              title={
                query || track || level
                  ? "Hier passt gerade kein Kapitel."
                  : tab === "bookmarks"
                    ? "Ein Gedanke darf auf dich warten."
                    : tab === "pins"
                      ? "Deine Pinnwand ist noch frei."
                      : "Die Bibliothek darf wachsen."
              }
              action={
                tab !== "library" && (
                  <button
                    className="button secondary"
                    onClick={() => {
                      setTab("library");
                      setQuery("");
                      setTrack("");
                      setLevel("");
                    }}
                  >
                    Bibliothek entdecken <Icon name="arrow" size={16} />
                  </button>
                )
              }
            >
              {query || track || level
                ? "Ändere deine Suche oder setze die Filter zurück."
                : tab === "bookmarks"
                  ? "Wähle bei einem Kapitel „Merken“, um es hier wiederzufinden."
                  : tab === "pins"
                    ? "Pinne Kapitel, die du in deiner Praxis immer wieder öffnen möchtest."
                    : "Bewusst veröffentlichte Kapitel erscheinen hier."}
            </Empty>
          )}
        </section>
      )}
      {tab === "notebook" && (
        <NotebookPanel
          {...props}
          notes={notebook.data}
          loading={notebook.loading}
          error={notebook.error}
          onCreate={() => createNote()}
          onEdit={(note) => setEditor({ note })}
        />
      )}
      {tab === "sources" && <SourcesPanel revision={props.revision} />}
      <div className="learning-boundary workspace-boundary">
        <Icon name="shield" size={19} />
        <p>
          Astrologie und Feldvorstellungen sind spirituelle Reflexionsansätze.
          Eigene Empfindung, Deutung und Rückmeldung bleiben unterscheidbar. Ein
          Quiz bestätigt Verständnisfragen, keine fachliche Qualifikation oder
          Heilwirkung.
        </p>
      </div>
      {selected && (
        <LessonReader
          key={selected.id}
          {...props}
          lesson={
            data.lessons.find((lesson) => lesson.id === selected.id) || selected
          }
          previousScore={data.progress.quiz_scores[String(selected.id)]}
          onClose={() => setSelected(null)}
          onUpdate={lessonUpdated}
          onCreateNote={createNote}
        />
      )}
      {editor && (
        <NotebookEditor
          {...props}
          {...editor}
          onClose={() => setEditor(null)}
          onSaved={(note) => {
            notebook.setData((current) =>
              current
                ? [note, ...current.filter((item) => item.id !== note.id)]
                : [note],
            );
            props.refresh();
          }}
        />
      )}
    </div>
  );
}

function LessonReader({
  lesson,
  onClose,
  previousScore,
  refresh,
  onUpdate,
  onCreateNote,
}: PageProps & {
  lesson: Lesson;
  previousScore?: number;
  onClose: () => void;
  onUpdate: (lesson: Lesson) => void;
  onCreateNote: (lesson: Lesson) => void;
}) {
  const [answers, setAnswers] = useState<Record<string, number>>({});
  const [result, setResult] = useState<{
    score: number;
    passed: boolean;
    feedback: string;
  } | null>(null);
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");
  const [saved, setSaved] = useState("");
  async function state(field: LessonState) {
    setBusy(field);
    setError("");
    setSaved("");
    try {
      const updated = await api<Lesson>(
        `/learning/${lesson.id}/state`,
        { [field]: !lesson[field] },
        "PATCH",
      );
      onUpdate(updated);
      setSaved("Dein Lernstand ist gespeichert.");
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy("");
    }
  }
  async function complete() {
    setBusy("complete");
    setError("");
    setSaved("");
    try {
      await api(`/learning/${lesson.id}/complete`, {});
      onUpdate({ ...lesson, completed: true });
      setSaved(
        "Als gelesen gespeichert. Übung und Reflexion kannst du unabhängig davon markieren.",
      );
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy("");
    }
  }
  async function quiz(event: FormEvent) {
    event.preventDefault();
    setBusy("quiz");
    setError("");
    try {
      setResult(await api(`/learning/${lesson.id}/quiz`, { answers }));
      refresh();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy("");
    }
  }
  return (
    <Modal
      title={lesson.title}
      description={`${lesson.track || lesson.category} · ${LEVELS[lesson.level] || "Grundlagen"}`}
      onClose={onClose}
      wide
    >
      <div className="lesson-reader workspace-reader">
        <p className="lesson-summary">{lesson.summary}</p>
        <div className="workspace-reader-tools">
          <button
            className="button secondary"
            aria-pressed={Boolean(lesson.bookmarked)}
            disabled={Boolean(busy)}
            onClick={() => void state("bookmarked")}
          >
            <Icon name="heart" size={17} />
            {lesson.bookmarked ? "Gemerkt" : "Merken"}
          </button>
          <button
            className="button secondary"
            aria-pressed={Boolean(lesson.pinned)}
            disabled={Boolean(busy)}
            onClick={() => void state("pinned")}
          >
            <Icon name="task" size={17} />
            {lesson.pinned ? "Gepinnt" : "Pinnen"}
          </button>
          <button
            className="button secondary"
            onClick={() => onCreateNote(lesson)}
          >
            <Icon name="note" size={17} />
            Eigene Notiz
          </button>
        </div>
        <ErrorBox error={error} />
        {saved && (
          <p className="workspace-feedback" role="status">
            <Icon name="check" size={16} />
            {saved}
          </p>
        )}
        {lesson.learning_objective && (
          <section className="workspace-reader-goal">
            <span className="small-label">DEIN LERNZIEL</span>
            <p>{lesson.learning_objective}</p>
          </section>
        )}
        <LessonSource lesson={lesson} />
        <div className="lesson-body">
          {lesson.body.split(/\n\n+/).map((paragraph, index) => (
            <p key={index}>{paragraph}</p>
          ))}
        </div>
        {lesson.exercise && (
          <section className="workspace-exercise">
            <span className="eyebrow">IN DIE EIGENE PRAXIS</span>
            <h3>Eine Übung für dich</h3>
            <p>{lesson.exercise}</p>
          </section>
        )}
        {lesson.reflection_prompt && (
          <section className="workspace-reflection">
            <span className="eyebrow">EIN MOMENT ZUM NACHSPÜREN</span>
            <h3>Deine Reflexionsfrage</h3>
            <p>{lesson.reflection_prompt}</p>
            <button className="text-link" onClick={() => onCreateNote(lesson)}>
              Im Notizbuch weiterdenken <Icon name="arrow" size={16} />
            </button>
          </section>
        )}
        <section className="workspace-checkin">
          <h3>Was hast du mitgenommen?</h3>
          <p>
            Markiere deine Schritte einzeln. Du entscheidest selbst, wann sie
            für dich passen.
          </p>
          <div>
            <button
              className={
                "button secondary " + (lesson.completed ? "marked" : "")
              }
              disabled={Boolean(busy) || lesson.completed}
              onClick={() => void complete()}
            >
              <Icon name={lesson.completed ? "check" : "book"} size={17} />
              {busy === "complete"
                ? "Wird gespeichert …"
                : lesson.completed
                  ? "Gelesen gespeichert"
                  : "Als gelesen markieren"}
            </button>
            <button
              className="button secondary"
              aria-pressed={Boolean(lesson.practiced)}
              disabled={Boolean(busy)}
              onClick={() => void state("practiced")}
            >
              <Icon name={lesson.practiced ? "check" : "leaf"} size={17} />
              {lesson.practiced ? "Geübt gespeichert" : "Als geübt markieren"}
            </button>
            <button
              className="button secondary"
              aria-pressed={Boolean(lesson.reflected)}
              disabled={Boolean(busy)}
              onClick={() => void state("reflected")}
            >
              <Icon name={lesson.reflected ? "check" : "note"} size={17} />
              {lesson.reflected
                ? "Reflektiert gespeichert"
                : "Als reflektiert markieren"}
            </button>
          </div>
        </section>
        {lesson.quiz.length > 0 && (
          <details className="workspace-optional-quiz">
            <summary>
              Freiwilliger Verständnischeck · {lesson.quiz.length}{" "}
              {lesson.quiz.length === 1 ? "Frage" : "Fragen"}
            </summary>
            <form onSubmit={quiz} className="lesson-quiz">
              <h3>Was nimmst du mit?</h3>
              <p>
                Du kannst diesen Check jederzeit machen. Er sperrt kein Kapitel
                und ist keine Voraussetzung für deine Lesebestätigung.
              </p>
              {lesson.quiz.map((question, index) => (
                <fieldset key={question.id}>
                  <legend>
                    {index + 1}. {question.question}
                  </legend>
                  {question.options.map((answer, option) => (
                    <label
                      className={
                        "quiz-option " +
                        (answers[question.id] === option ? "selected" : "")
                      }
                      key={option}
                    >
                      <input
                        type="radio"
                        name={question.id}
                        required
                        checked={answers[question.id] === option}
                        onChange={() => {
                          setAnswers((current) => ({
                            ...current,
                            [question.id]: option,
                          }));
                          setResult(null);
                        }}
                      />
                      <span>{answer}</span>
                    </label>
                  ))}
                </fieldset>
              ))}
              <button
                className="button secondary"
                disabled={
                  Boolean(busy) ||
                  Object.keys(answers).length !== lesson.quiz.length
                }
              >
                {busy === "quiz" ? "Wird geprüft …" : "Antworten prüfen"}
                <Icon name="check" size={16} />
              </button>
            </form>
            {result ? (
              <div
                className={"alert " + (result.passed ? "success" : "")}
                role="status"
              >
                <Icon name={result.passed ? "check" : "leaf"} />
                <div>
                  <strong>{result.score}% im Verständnischeck</strong>
                  <p>{result.feedback}</p>
                </div>
              </div>
            ) : (
              previousScore !== undefined && (
                <p className="workspace-feedback">
                  Dein bestes gespeichertes Quizergebnis: {previousScore}%.
                </p>
              )
            )}
          </details>
        )}
        <div className="form-actions">
          <button className="button secondary" onClick={onClose}>
            Zurück zum Lernraum <Icon name="arrow" size={17} />
          </button>
        </div>
      </div>
    </Modal>
  );
}

function NotebookPanel({
  notes,
  loading,
  error,
  onCreate,
  onEdit,
  notify,
}: PageProps & {
  notes: NotebookNote[] | null;
  loading: boolean;
  error: string;
  onCreate: () => void;
  onEdit: (note: NotebookNote) => void;
}) {
  const [exporting, setExporting] = useState(false);
  const [exportError, setExportError] = useState("");
  const [search, setSearch] = useState("");
  async function exportNotes() {
    setExporting(true);
    setExportError("");
    try {
      const result = await api<{ filename: string; content: string }>(
        "/learning/notebook/export",
      );
      const url = URL.createObjectURL(
        new Blob([result.content], { type: "text/markdown;charset=utf-8" }),
      );
      const link = document.createElement("a");
      link.href = url;
      link.download = result.filename;
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.setTimeout(() => URL.revokeObjectURL(url), 1000);
      notify("Der Markdown-Export wurde an den Browser übergeben.");
    } catch (e) {
      setExportError((e as Error).message);
    } finally {
      setExporting(false);
    }
  }
  const visible = (notes || []).filter((note) =>
    [note.title, note.body, note.lesson_title_snapshot]
      .join(" ")
      .toLocaleLowerCase("de")
      .includes(search.trim().toLocaleLowerCase("de")),
  );
  return (
    <section className="workspace-notebook">
      <div className="workspace-section-heading">
        <div>
          <h2>Dein privates Notizbuch.</h2>
          <p>
            Eigene Gedanken, Übungen und Erfahrungen – frei oder mit einem
            Kapitel verknüpft.
          </p>
        </div>
        <div className="workspace-reader-tools">
          <button
            className="button secondary"
            disabled={exporting || !notes?.length}
            onClick={() => void exportNotes()}
          >
            <Icon name="download" size={17} />
            {exporting ? "Export wird vorbereitet …" : "Markdown exportieren"}
          </button>
          <button className="button primary purple-button" onClick={onCreate}>
            <Icon name="plus" size={17} />
            Neue Notiz
          </button>
        </div>
      </div>
      <p className="workspace-private">
        <Icon name="lock" size={16} />
        Nur dein angemeldetes Konto hat Zugriff auf diese Lernnotizen. Verwende
        für Übungsfälle anonymisierte Angaben.
      </p>
      <ErrorBox error={error || exportError} />
      {loading && !notes ? (
        <Loading />
      ) : !notes && error ? (
        <p className="workspace-help">
          Deine Notizen konnten nicht geladen werden. Öffne den Bereich erneut,
          um es nochmals zu versuchen.
        </p>
      ) : notes?.length ? (
        <>
          <label className="workspace-note-search">
            Notizen durchsuchen
            <input
              type="search"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Titel, Text oder Kapitel"
            />
          </label>
          <div className="workspace-note-list">
            {visible.map((note) => (
              <article className="glass-card workspace-note" key={note.id}>
                <div className="workspace-note-top">
                  <Badge tone="purple">
                    {note.lesson_id !== null ? "Kapitelnotiz" : "Freie Notiz"}
                  </Badge>
                  <span>Bearbeitet {dateFormat(note.updated_at)}</span>
                </div>
                <h3>{note.title}</h3>
                {note.lesson_title_snapshot && (
                  <p className="workspace-note-context">
                    {note.lesson_title_snapshot} · Inhaltsversion{" "}
                    {note.lesson_version_snapshot ?? "unbekannt"} bei
                    Verknüpfung
                  </p>
                )}
                <p className="workspace-note-body">{note.body}</p>
                <button className="text-link" onClick={() => onEdit(note)}>
                  Notiz bearbeiten <Icon name="note" size={16} />
                </button>
              </article>
            ))}
          </div>
          {!visible.length && (
            <Empty icon="search" title="Keine passende Notiz.">
              Ändere deinen Suchbegriff, um andere Gedanken wiederzufinden.
            </Empty>
          )}
        </>
      ) : (
        <Empty
          icon="note"
          title="Ein eigener Gedanke ist ein Anfang."
          action={
            <button className="button secondary" onClick={onCreate}>
              Deine erste Notiz schreiben <Icon name="plus" size={16} />
            </button>
          }
        >
          Beginne mit einer freien Notiz oder öffne ein Kapitel und wähle
          „Eigene Notiz“.
        </Empty>
      )}
    </section>
  );
}

function NotebookEditor({
  note,
  lesson,
  onClose,
  onSaved,
  notify,
}: PageProps & {
  note?: NotebookNote;
  lesson?: Lesson;
  onClose: () => void;
  onSaved: (note: NotebookNote) => void;
}) {
  const initialTitle =
    note?.title || (lesson ? `Gedanken zu: ${lesson.title}`.slice(0, 160) : "");
  const [title, setTitle] = useState(initialTitle);
  const [body, setBody] = useState(note?.body || "");
  const [baseline, setBaseline] = useState({
    title: initialTitle,
    body: note?.body || "",
  });
  const [currentNote, setCurrentNote] = useState(note);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [savedAt, setSavedAt] = useState("");
  const [discard, setDiscard] = useState(false);
  const [leaveHash, setLeaveHash] = useState<string | null>(null);
  const dirty = title !== baseline.title || body !== baseline.body;
  // Event handlers update this synchronously; navigation must not wait for a React effect.
  const guard = useRef({
    dirty: false,
    busy: false,
    enabled: true,
    title: initialTitle,
    body: note?.body || "",
    baselineTitle: initialTitle,
    baselineBody: note?.body || "",
  });
  useLayoutEffect(() => {
    const currentUrl = window.location.href;
    const protectedDraft = () =>
      guard.current.enabled && (guard.current.dirty || guard.current.busy);
    const keepDraft = (event: HashChangeEvent | PopStateEvent) => {
      if (!protectedDraft() || window.location.href === currentUrl) return;
      const destination = window.location.hash;
      // Capture before useRoute. popstate can precede the hashchange during Back.
      event.stopImmediatePropagation();
      window.history.replaceState(window.history.state, "", currentUrl);
      if (!guard.current.busy) {
        setLeaveHash(destination);
        setDiscard(true);
      }
    };
    const warn = (event: BeforeUnloadEvent) => {
      if (!protectedDraft()) return;
      event.preventDefault();
      event.returnValue = "Unsaved changes";
    };
    window.addEventListener("beforeunload", warn);
    window.addEventListener("popstate", keepDraft, true);
    window.addEventListener("hashchange", keepDraft, true);
    return () => {
      window.removeEventListener("beforeunload", warn);
      window.removeEventListener("popstate", keepDraft, true);
      window.removeEventListener("hashchange", keepDraft, true);
    };
  }, []);
  function changeDraft(field: "title" | "body", value: string) {
    if (guard.current.busy) return;
    guard.current[field] = value;
    guard.current.dirty =
      guard.current.title !== guard.current.baselineTitle ||
      guard.current.body !== guard.current.baselineBody;
    if (field === "title") setTitle(value);
    else setBody(value);
  }
  function requestClose() {
    if (guard.current.busy) return;
    if (guard.current.dirty) setDiscard(true);
    else onClose();
  }
  function discardChanges() {
    // An explicit discard must also let the user's confirmed destination through.
    guard.current.enabled = false;
    guard.current.dirty = false;
    onClose();
    if (leaveHash !== null) window.location.hash = leaveHash;
  }
  async function save(event: FormEvent) {
    event.preventDefault();
    if (guard.current.busy) return;
    guard.current.busy = true;
    const snapshot = {
      title: guard.current.title.trim(),
      body: guard.current.body.trim(),
    };
    setBusy(true);
    setError("");
    setSavedAt("");
    try {
      const result = currentNote
        ? await api<NotebookNote>(
            `/learning/notebook/${currentNote.id}`,
            snapshot,
            "PATCH",
          )
        : await api<NotebookNote>("/learning/notebook", {
            lesson_id: lesson?.id ?? null,
            ...snapshot,
          });
      Object.assign(guard.current, {
        dirty: false,
        title: result.title,
        body: result.body,
        baselineTitle: result.title,
        baselineBody: result.body,
      });
      setCurrentNote(result);
      setTitle(result.title);
      setBody(result.body);
      setBaseline({ title: result.title, body: result.body });
      setSavedAt(result.updated_at);
      onSaved(result);
      notify("Deine private Notiz ist gespeichert.");
    } catch (e) {
      setError((e as Error).message);
    } finally {
      guard.current.busy = false;
      setBusy(false);
    }
  }
  const snapshotTitle = currentNote?.lesson_title_snapshot || lesson?.title;
  const snapshotVersion =
    currentNote?.lesson_version_snapshot ?? lesson?.content_version;
  return (
    <Modal
      title={
        currentNote ? "Deine Notiz weiterdenken." : "Raum für deinen Gedanken."
      }
      description="Privates Lernnotizbuch · keine Weitergabe an Klienten oder Recherche-Dienste."
      onClose={requestClose}
      wide
    >
      {discard ? (
        <div className="workspace-discard" role="alert">
          <h3>Deine Änderungen sind noch nicht gespeichert.</h3>
          <p>
            Du kannst weiterschreiben und speichern oder diese Änderungen
            verwerfen. Eine bereits gespeicherte Notiz bleibt erhalten.
          </p>
          <div className="form-actions">
            <button
              autoFocus
              className="button primary purple-button"
              onClick={() => {
                setDiscard(false);
                setLeaveHash(null);
              }}
            >
              Weiter bearbeiten
            </button>
            <button className="button secondary" onClick={discardChanges}>
              Änderungen verwerfen
            </button>
          </div>
        </div>
      ) : (
        <form
          className="workspace-note-editor"
          onSubmit={save}
          aria-busy={busy}
        >
          {snapshotTitle && (
            <div className="workspace-note-context">
              <strong>Verknüpft mit: {snapshotTitle}</strong>
              <p>
                Inhaltsversion {snapshotVersion || 1} bei Verknüpfung. Dieser
                Bezug bleibt auch bei späteren Kapiteländerungen erhalten.
              </p>
            </div>
          )}
          <label>
            Titel
            <input
              autoFocus
              required
              maxLength={160}
              value={title}
              readOnly={busy}
              onChange={(e) => changeDraft("title", e.target.value)}
            />
          </label>
          <label>
            Deine Notiz
            <textarea
              required
              rows={12}
              maxLength={12000}
              value={body}
              readOnly={busy}
              onChange={(e) => changeDraft("body", e.target.value)}
              placeholder="Was habe ich wahrgenommen? Wie deute ich es? Welche tatsächliche Rückmeldung gab es?"
            />
            <small>
              {body.length.toLocaleString("de-DE")} / 12.000 Zeichen · Texte
              werden als Text gespeichert.
            </small>
          </label>
          <p className="workspace-private">
            <Icon name="lock" size={16} />
            Nutze anonymisierte Beispiele. Die Notiz ist deinem Konto
            zugeordnet.
          </p>
          <ErrorBox error={error} />
          {savedAt && !dirty && (
            <p className="workspace-feedback" role="status">
              <Icon name="check" size={16} />
              Gespeichert am{" "}
              {dateFormat(savedAt, {
                day: "2-digit",
                month: "2-digit",
                year: "numeric",
                hour: "2-digit",
                minute: "2-digit",
              })}
              .
            </p>
          )}
          <div className="form-actions">
            <button
              type="button"
              className="button text"
              disabled={busy}
              onClick={requestClose}
            >
              Schließen
            </button>
            <span className="workspace-draft-state" role="status">
              {busy
                ? "Wird gespeichert – Eingabefelder kurz schreibgeschützt"
                : dirty
                  ? "Ungespeicherte Änderungen"
                  : savedAt || currentNote
                    ? "Alle Änderungen gespeichert"
                    : "Neue Notiz"}
            </span>
            <button
              className="button primary purple-button"
              disabled={
                busy ||
                !title.trim() ||
                !body.trim() ||
                (Boolean(currentNote) && !dirty)
              }
            >
              <Icon name="note" size={17} />
              {busy ? "Wird gespeichert …" : "Notiz speichern"}
            </button>
          </div>
        </form>
      )}
    </Modal>
  );
}

const SOURCES = [
  {
    name: "Silke Schäfer",
    language: "Deutsch",
    area: "Spirituelle Astrologie & Selbsterfahrung",
    text: "Öffentliche Beiträge als Zugang zur astrologischen Symbolsprache. Grundausbildung und professionelle Ausbildung sind eigenständige Angebote.",
    url: "https://www.silkeschaefer.com/astrologie/aktuelles",
    label: "Öffentliche Beiträge",
  },
  {
    name: "Mark Jones",
    language: "Englisch",
    area: "Beratungspräsenz & transpersonale Perspektive",
    text: "Das öffentliche Interview beschreibt seine Vorstellung eines „Knowing Field“. Diese Feldvorstellung ist eine spirituelle Aussage des Autors, kein Nachweis von Fernwahrnehmung.",
    url: "https://markjonesastrology.com/blog/therapeutic-potential-astrology/",
    label: "Interview zur Beratung",
  },
  {
    name: "Kaypacha / New Paradigm Astrology",
    language: "Englisch",
    area: "Evolutionäre Astrologie",
    text: "Pele Reports und öffentliche Impulse verbinden astrologische Deutung mit spirituellem Seelenbezug. Kostenpflichtige Bibliothek und Ausbildung bleiben getrennte Angebote.",
    url: "https://newparadigmastrology.com/",
    label: "Öffentlicher Einstieg",
  },
  {
    name: "Maurice Fernandez",
    language: "Deutsch / Englisch",
    area: "Evolutionäre Astrologie & Vertiefung",
    text: "Ein Vergleichszugang zu einer evolutionären Schule. Reinkarnation und Seelenentwicklung sind Lehrannahmen dieses Ansatzes.",
    url: "https://mauricefernandez.com/was-ist-evolutionare-astrologie/",
    label: "Einführung auf Deutsch",
  },
  {
    name: "Pam Gregory",
    language: "Englisch",
    area: "Meditation & spirituelle Reflexion",
    text: "Öffentliche Meditationen ergänzen die eigene Reflexionspraxis. Zeitbezogene Impulse ersetzen keinen zusammenhängenden Grundlagenlehrgang.",
    url: "https://www.thenextstep.uk.com/meditation/",
    label: "Öffentliche Meditationen",
  },
];
const UPDATE_STATUS: Record<string, string> = {
  succeeded: "Abgeschlossen",
  partial: "Teilweise abgeschlossen",
  failed: "Fehlgeschlagen",
  running: "Läuft",
  stale: "Unterbrochen",
  not_due: "Noch nicht fällig",
  disabled: "Ausgeschaltet",
};
function updateTime(value: string | null | undefined) {
  return value
    ? dateFormat(value, {
        day: "2-digit",
        month: "2-digit",
        year: "numeric",
        hour: "2-digit",
        minute: "2-digit",
      }) + " Uhr (Berlin)"
    : "Noch nicht vorhanden";
}
function SourceReports({ sources }: { sources: LearningUpdateSource[] }) {
  return (
    <ul>
      {sources.map((source) => (
        <li key={source.key}>
          <strong>{source.title}</strong>
          {source.fetch_status && (
            <p>
              {source.fetch_status === "index_accessible"
                ? `Index erreichbar · ${source.candidates || 0} Beitragsverweise gefunden`
                : "Nicht vollständig abrufbar"}
              {source.fetched_at ? " · " + updateTime(source.fetched_at) : ""}
            </p>
          )}
          <a
            className="text-link"
            href={source.url}
            target="_blank"
            rel="noopener noreferrer"
          >
            Original öffnen <Icon name="arrow" size={14} />
          </a>
        </li>
      ))}
    </ul>
  );
}
function UpdateStatusPanel({
  data,
  loading,
  error,
}: {
  data: LearningUpdatesStatus | null;
  loading: boolean;
  error: string;
}) {
  return (
    <div className="glass-card workspace-update-status">
      <Icon name="refresh" size={23} />
      <div>
        <span className="small-label">
          QUELLENPRÜFUNG · ENTWÜRFE MIT REDAKTION
        </span>
        <h3>
          {data
            ? `Alle ${data.interval_days} Tage · ${data.enabled ? "Abruf eingeschaltet" : "Abruf ausgeschaltet"}`
            : error
              ? "Aktualisierungsstatus zurzeit nicht verfügbar"
              : "Aktualisierungsstatus laden"}
        </h3>
        <ErrorBox error={error} />
        {loading && !data ? (
          <Loading />
        ) : (
          data && (
            <>
              <p>
                Neue Quellenfunde landen als unveröffentlichte Rechercheentwürfe
                im Lernraum. Ein eigener Lehrtext, die fachliche Prüfung und die
                Veröffentlichung bleiben bewusste redaktionelle Schritte.
              </p>
              <dl className="admin-preview-metadata">
                <div>
                  <dt>Letzter Lauf</dt>
                  <dd>{updateTime(data.last_run_at)}</dd>
                </div>
                <div>
                  <dt>Ergebnis</dt>
                  <dd>
                    {data.last_run_status
                      ? UPDATE_STATUS[data.last_run_status] ||
                        data.last_run_status
                      : "Noch kein Lauf"}
                  </dd>
                </div>
                <div>
                  <dt>Nächste Fälligkeit</dt>
                  <dd>{updateTime(data.next_due_at)}</dd>
                </div>
                <div>
                  <dt>Letzter vollständig erfolgreicher Lauf</dt>
                  <dd>{updateTime(data.last_success_at)}</dd>
                </div>
              </dl>
              {data.active_run && !data.stale && (
                <p role="status">Ein Quellenlauf wird gerade verarbeitet.</p>
              )}
              {data.stale && (
                <div className="alert" role="status">
                  Ein früherer Quellenlauf wurde unterbrochen. Er muss beim
                  nächsten Aufruf erneut geprüft werden.
                </div>
              )}
              {data.last_error && <ErrorBox error={data.last_error} />}
              <p className="fineprint">
                Diese Anzeige liest den gespeicherten Abrufstatus. Der Zeitplan
                wird separat betrieben. Ob ein Abruf tatsächlich stattgefunden
                hat, erkennst du an den protokollierten Läufen; „eingeschaltet“
                allein bestätigt noch keinen laufenden Zeitplan. Es wird nichts
                automatisch veröffentlicht.
              </p>
              <details className="review-details">
                <summary>
                  Laufhistorie · {data.recent_runs.length} letzte Läufe
                </summary>
                {data.recent_runs.length ? (
                  data.recent_runs.map((run) => (
                    <article key={run.id} className="admin-preview-section">
                      <h4>
                        {UPDATE_STATUS[run.status] || run.status} ·{" "}
                        {run.created} neue Entwürfe
                      </h4>
                      <p>
                        {updateTime(run.started_at)} ·{" "}
                        {run.trigger === "cron"
                          ? "Zeitplanaufruf"
                          : "Manuell angestoßen"}
                      </p>
                      {run.finished_at && (
                        <p>Beendet: {updateTime(run.finished_at)}</p>
                      )}
                      {run.error && <ErrorBox error={run.error} />}
                      <SourceReports sources={run.sources} />
                    </article>
                  ))
                ) : (
                  <p>Noch kein Quellenlauf protokolliert.</p>
                )}
              </details>
              <details className="review-details">
                <summary>
                  Konfigurierte öffentliche Quellen · {data.sources.length}
                </summary>
                <SourceReports sources={data.sources} />
              </details>
              {data.findings.length > 0 && (
                <details className="review-details">
                  <summary>
                    Zuletzt gefundene Originale · {data.findings.length}
                  </summary>
                  <ul>
                    {data.findings.map((finding) => (
                      <li key={finding.url}>
                        <a
                          className="text-link"
                          href={finding.url}
                          target="_blank"
                          rel="noopener noreferrer"
                        >
                          {finding.title}
                          <Icon name="arrow" size={14} />
                        </a>
                        <p>
                          {finding.fetch_status === "text_accessible"
                            ? "Webtext technisch zugänglich, fachlich ungeprüft"
                            : finding.fetch_status === "metadata_only"
                              ? "Nur Fundmetadaten zugänglich"
                              : "Abruf unvollständig"}{" "}
                          · {updateTime(finding.fetched_at)}
                          {finding.lesson_id
                            ? ` · Entwurf #${finding.lesson_id}`
                            : ""}
                        </p>
                      </li>
                    ))}
                  </ul>
                </details>
              )}
            </>
          )
        )}
      </div>
    </div>
  );
}
function SourcesPanel({ revision }: { revision: number }) {
  const updates = useData<LearningUpdatesStatus>(
    "/learning/updates/status",
    revision,
  );
  return (
    <section className="workspace-sources">
      <div className="workspace-section-heading">
        <div>
          <h2>Perspektiven im Original.</h2>
          <p>
            Eine redaktionelle Auswahl öffentlicher Einstiegsquellen –
            verschiedene Schulen bleiben als solche erkennbar.
          </p>
        </div>
      </div>
      <UpdateStatusPanel
        data={updates.data}
        loading={updates.loading}
        error={updates.error}
      />
      <div className="workspace-source-grid">
        {SOURCES.map((source) => (
          <article className="glass-card workspace-source" key={source.name}>
            <span className="small-label">{source.language}</span>
            <h3>{source.name}</h3>
            <strong>{source.area}</strong>
            <p>{source.text}</p>
            <a
              className="text-link"
              href={source.url}
              target="_blank"
              rel="noopener noreferrer"
            >
              {source.label}
              <Icon name="arrow" size={16} />
            </a>
          </article>
        ))}
      </div>
      <p className="workspace-source-note">
        Die Links führen zu externen Originalen. Öffentliche Einstiege können
        auf kostenpflichtige Angebote verweisen; ein Kauf ist für diesen
        Lernraum nicht nötig. Die Auswahl behauptet keine Zusammenarbeit oder
        Empfehlung durch die genannten Lehrenden. SoulFlow-Lektionen sind
        eigenständige Texte, keine Kopien ihrer Kurse.
      </p>
    </section>
  );
}

function AdminLessonPreview({ lesson }: { lesson: AdminLesson }) {
  return (
    <div className="admin-lesson-preview">
      <dl className="admin-preview-metadata">
        <div>
          <dt>Themenraum</dt>
          <dd>{lesson.track || lesson.category}</dd>
        </div>
        <div>
          <dt>Niveau</dt>
          <dd>{LEVELS[lesson.level] || "Grundlagen"}</dd>
        </div>
        <div>
          <dt>Inhaltsversion</dt>
          <dd>{lesson.content_version || 1}</dd>
        </div>
      </dl>
      <section>
        <h4>Lernziel</h4>
        <p>
          {lesson.learning_objective || "Noch kein eigenes Lernziel angegeben."}
        </p>
      </section>
      <LessonSource lesson={lesson} />
      {!lesson.source_note && (
        <p className="fineprint">
          Noch kein zusätzlicher Quellenhinweis angegeben.
        </p>
      )}
      <section>
        <h4>Lektionstext</h4>
        <div className="lesson-body">
          {lesson.body.split(/\n\n+/).map((paragraph, index) => (
            <p key={index}>{paragraph}</p>
          ))}
        </div>
      </section>
      <section>
        <h4>Übung</h4>
        <p>{lesson.exercise || "Noch keine separate Übung angegeben."}</p>
      </section>
      <section>
        <h4>Reflexionsfrage</h4>
        <p>
          {lesson.reflection_prompt ||
            "Noch keine separate Reflexionsfrage angegeben."}
        </p>
      </section>
      <section className="admin-preview-quiz">
        <h4>
          Freiwilliger Verständnischeck · {lesson.quiz.length}{" "}
          {lesson.quiz.length === 1 ? "Frage" : "Fragen"}
        </h4>
        <p className="fineprint">
          Korrekte Antworten sind nur in dieser Adminvorschau sichtbar. Der
          Check ist keine Voraussetzung für den Bibliothekszugang oder die
          Lesebestätigung.
        </p>
        {lesson.quiz.length ? (
          <ol>
            {lesson.quiz.map((question) => (
              <li key={question.id}>
                <strong>{question.question}</strong>
                <ol type="A">
                  {question.options.map((option, index) => (
                    <li key={index}>
                      <span>{option}</span>
                      {question.correct_index === index && (
                        <Badge tone="green">
                          <Icon name="check" size={14} />
                          Korrekte Antwort
                        </Badge>
                      )}
                    </li>
                  ))}
                </ol>
                {!Number.isInteger(question.correct_index) && (
                  <p className="fineprint">
                    Die korrekte Antwort fehlt in der Adminantwort. Vor der
                    Freigabe prüfen.
                  </p>
                )}
              </li>
            ))}
          </ol>
        ) : (
          <p>Keine Quizfrage vorhanden.</p>
        )}
      </section>
    </div>
  );
}

export function AdminPage(props: PageProps) {
  const { data, loading, error } = useData<AdminLesson[]>(
    "/admin/lessons",
    props.revision,
  );
  const updates = useData<LearningUpdatesStatus>(
    "/learning/updates/status",
    props.revision,
  );
  const [updateResult, setUpdateResult] = useState<LearningUpdateResult | null>(
    null,
  );
  const actionLock = useRef(false);
  const [create, setCreate] = useState(false),
    [sourceDraft, setSourceDraft] = useState<AdminLesson | null>(null),
    [publish, setPublish] = useState<Lesson | null>(null),
    [busy, setBusy] = useState(""),
    [actionError, setActionError] = useState(""),
    [scan, setScan] = useState<{
      mode: string;
      created: number;
      message: string;
      sources: unknown[];
    } | null>(null);
  async function runScan() {
    if (actionLock.current) return;
    actionLock.current = true;
    setBusy("scan");
    setActionError("");
    try {
      const result = await api<{
        mode: string;
        created: number;
        message: string;
        sources: unknown[];
      }>("/admin/scan", { simulate: true });
      setScan(result);
      props.refresh();
      props.notify(
        "Die Wochen-Simulation ist abgeschlossen. Neue Inhalte bleiben Entwürfe.",
      );
    } catch (e) {
      setActionError((e as Error).message);
    } finally {
      actionLock.current = false;
      setBusy("");
    }
  }
  async function runSourceUpdate() {
    if (actionLock.current) return;
    actionLock.current = true;
    setBusy("updates");
    setActionError("");
    setUpdateResult(null);
    try {
      const response = await fetch("/api/admin/learning-updates/run", {
        method: "POST",
        credentials: "same-origin",
        cache: "no-store",
        headers: { "Content-Type": "application/json", "X-SoulFlow": "1" },
        body: "{}",
      });
      const result = (await response.json()) as LearningUpdateResult & {
        detail?: string;
      };
      if (
        !result.status ||
        (!response.ok &&
          !["partial", "failed", "stale"].includes(result.status))
      )
        throw new Error(
          result.detail || "Der Quellenlauf konnte nicht abgerufen werden.",
        );
      setUpdateResult(result);
      if (result.status === "succeeded")
        props.notify(
          `Der Quellenlauf ist abgeschlossen. ${result.created} neue Entwürfe warten auf die Redaktion.`,
        );
    } catch (e) {
      setActionError((e as Error).message);
    } finally {
      props.refresh();
      actionLock.current = false;
      setBusy("");
    }
  }
  async function publishLesson() {
    if (!publish || isSourceDraft(publish) || actionLock.current) return;
    actionLock.current = true;
    setBusy("publish");
    setActionError("");
    try {
      await api(`/admin/lessons/${publish.id}/publish`, {});
      setPublish(null);
      props.refresh();
      props.notify(
        "Der geprüfte Lernimpuls ist veröffentlicht und für alle Lernenden offen.",
      );
    } catch (e) {
      setActionError((e as Error).message);
    } finally {
      actionLock.current = false;
      setBusy("");
    }
  }
  return (
    <>
      <div className="page-heading">
        <div>
          <span className="eyebrow">WISSEN BEWUSST WEITERGEBEN</span>
          <h1>
            Impulse mit Verantwortung. <ContextHelp topic="learning" />
          </h1>
          <p>Entwürfe prüfen, Quellen sichtbar halten und bewusst freigeben.</p>
        </div>
        <button
          className="button primary purple-button"
          disabled={!!busy}
          onClick={() => {
            setSourceDraft(null);
            setCreate(true);
          }}
        >
          <Icon name="plus" size={17} /> Lernimpuls anlegen
        </button>
      </div>
      <UpdateStatusPanel
        data={updates.data}
        loading={updates.loading}
        error={updates.error}
      />
      <div className="admin-scan glass-card">
        <span className="card-icon crown">
          <Icon name="refresh" size={24} />
        </span>
        <div>
          <span className="eyebrow">ECHTER QUELLENLAUF · ALLE 14 TAGE</span>
          <h2>Neue Originale finden. In Ruhe redigieren.</h2>
          <p>
            Prüft ausschließlich konfigurierte öffentliche Quellen. Neue Funde
            bleiben Rechercheentwürfe. Der Aufruf respektiert die gespeicherte
            Fälligkeit und veröffentlicht keine Lektionen.
          </p>
          {updates.data?.next_due_at && (
            <p className="fineprint">
              Nächste Fälligkeit: {updateTime(updates.data.next_due_at)}
            </p>
          )}
        </div>
        <button
          className="button secondary"
          disabled={
            !!busy ||
            !updates.data?.enabled ||
            (!!updates.data?.active_run && !updates.data?.stale) ||
            (!!updates.data?.next_due_at &&
              new Date(updates.data.next_due_at).getTime() > Date.now())
          }
          onClick={() => void runSourceUpdate()}
        >
          {busy === "updates"
            ? "Quellen werden geprüft …"
            : "Fälligen Quellenlauf starten"}
          <Icon name="refresh" size={17} />
        </button>
      </div>
      {updateResult && (
        <div
          className={
            "alert " + (updateResult.status === "succeeded" ? "success" : "")
          }
          role="status"
        >
          <Icon name={updateResult.status === "succeeded" ? "check" : "note"} />
          <div>
            <strong>
              {UPDATE_STATUS[updateResult.status] || updateResult.status} ·{" "}
              {updateResult.created} neue Entwürfe
            </strong>
            {updateResult.next_due_at && (
              <p>Nächste Fälligkeit: {updateTime(updateResult.next_due_at)}</p>
            )}
            {updateResult.error && <p>{updateResult.error}</p>}
            {updateResult.sources && (
              <details>
                <summary>Ergebnisse der öffentlichen Quellenprüfung</summary>
                <SourceReports sources={updateResult.sources} />
              </details>
            )}
          </div>
        </div>
      )}
      <details className="review-details">
        <summary>Optional: Quellenlauf mit Beispieldaten simulieren</summary>
        <div className="admin-scan glass-card">
          <span className="card-icon crown">
            <Icon name="refresh" size={24} />
          </span>
          <div>
            <span className="eyebrow">MANUELLER QUELLENBLICK · SIMULATION</span>
            <h2>Neue Perspektiven. Bewusste Auswahl.</h2>
            <p>
              Die lokale Simulation erzeugt gekennzeichnete Beispielentwürfe.
              Keine automatische Veröffentlichung und keine externe KI-Anfrage.
            </p>
          </div>
          <button
            className="button secondary"
            disabled={!!busy}
            onClick={() => void runScan()}
          >
            {busy === "scan" ? "Simulation läuft …" : "Wochen-Scan simulieren"}
            <Icon name="spark" size={17} />
          </button>
        </div>
        {scan && (
          <div className="alert success" role="status">
            <Icon name="check" />
            <div>
              <strong>Simulation · {scan.created} neue Entwürfe</strong>
              <p>{scan.message}</p>
              {scan.sources.length > 0 && (
                <details>
                  <summary>Verwendete Beispielquellen</summary>
                  <pre className="source-json">
                    {JSON.stringify(scan.sources, null, 2)}
                  </pre>
                </details>
              )}
            </div>
          </div>
        )}
      </details>
      <ErrorBox error={error || actionError} />
      <section className="glass-card admin-lessons">
        <SectionTitle
          title="Deine Lernimpulse"
          eyebrow="ENTWURF → PRÜFUNG → FREIGABE"
        />
        <p className="fineprint">
          Astrologische Inhalte bleiben als spirituelle Deutung erkennbar.
          Psychologische Aussagen benötigen eine belastbare Quelle.
          Veröffentliche keine Heilversprechen.
        </p>
        {loading && !data ? (
          <Loading />
        ) : data?.length ? (
          <div className="admin-lesson-list">
            {data.map((lesson) => (
              <article className="admin-lesson" key={lesson.id}>
                <div className="lesson-week">
                  POSITION<strong>{lesson.week}</strong>
                </div>
                <div className="admin-lesson-main">
                  <div className="inline-badges">
                    <Badge
                      tone={lesson.status === "published" ? "green" : "purple"}
                    >
                      {lesson.status === "published"
                        ? "Veröffentlicht"
                        : isSourceDraft(lesson)
                          ? "Quellenentwurf · redaktionell ungeprüft"
                          : "Entwurf"}
                    </Badge>
                    <span className="small-label">{lesson.category}</span>
                  </div>
                  <h3>{lesson.title}</h3>
                  <p>{lesson.summary}</p>
                  <details className="review-details">
                    <summary>Inhalt & Quelle prüfen</summary>
                    <AdminLessonPreview lesson={lesson} />
                  </details>
                </div>
                {lesson.status === "draft" ? (
                  <div className="button-pair">
                    <button
                      className="button secondary small"
                      disabled={!!busy}
                      onClick={() => {
                        setSourceDraft(lesson);
                        setCreate(true);
                      }}
                    >
                      {isSourceDraft(lesson)
                        ? "Quellenentwurf redigieren"
                        : "Entwurf bearbeiten"}
                      <Icon name="note" size={15} />
                    </button>
                    {!isSourceDraft(lesson) && (
                      <button
                        className="button secondary small"
                        disabled={!!busy}
                        onClick={() => {
                          setActionError("");
                          setPublish(lesson);
                        }}
                      >
                        Bewusst freigeben
                        <Icon name="eye" size={15} />
                      </button>
                    )}
                  </div>
                ) : (
                  <span className="published-check">
                    <Icon name="check" size={20} />
                  </span>
                )}
              </article>
            ))}
          </div>
        ) : (
          <Empty icon="book" title="Hier beginnt dein Wissensraum.">
            Erstelle einen quellengebundenen Lernimpuls oder starte die
            Simulation.
          </Empty>
        )}
      </section>
      {create && (
        <LessonForm
          {...props}
          sourceDraft={sourceDraft}
          nextWeek={
            Array.from({ length: 260 }, (_, index) => index + 1).find(
              (position) =>
                (data || []).every((lesson) => lesson.week !== position),
            ) || 260
          }
          onClose={() => setCreate(false)}
        />
      )}{" "}
      {publish && (
        <Modal
          title="Diesen Impuls veröffentlichen?"
          description={publish.title}
          onClose={() => {
            if (!actionLock.current) setPublish(null);
          }}
        >
          <div className="alert">
            <Icon name="shield" />
            <p>
              Mit der Freigabe wird dieser Inhalt sofort in der offenen
              Bibliothek sichtbar. Prüfe vorher Inhalt, Quelle, Quiz und die
              klare Trennung von Fachwissen und spiritueller Deutung.
            </p>
          </div>
          <ErrorBox error={actionError} />
          <div className="form-actions">
            <button
              className="button text"
              disabled={!!busy}
              onClick={() => setPublish(null)}
            >
              Weiter prüfen
            </button>
            <button
              disabled={busy === "publish"}
              className="button primary purple-button"
              onClick={() => void publishLesson()}
            >
              {busy === "publish"
                ? "Wird veröffentlicht …"
                : "Geprüft und bewusst freigeben"}
              <Icon name="check" size={17} />
            </button>
          </div>
        </Modal>
      )}
    </>
  );
}
function LessonForm({
  onClose,
  refresh,
  notify,
  nextWeek,
  sourceDraft,
}: PageProps & {
  onClose: () => void;
  nextWeek: number;
  sourceDraft: AdminLesson | null;
}) {
  const [busy, setBusy] = useState(false),
    [error, setError] = useState("");
  const [quiz, setQuiz] = useState<AdminLesson["quiz"]>(() =>
    sourceDraft?.quiz.length
      ? sourceDraft.quiz.map((question) => ({
          ...question,
          options: [...question.options],
        }))
      : [{ id: "q1", question: "", options: ["", "", ""], correct_index: 0 }],
  );
  const [discard, setDiscard] = useState(false),
    [leaveHash, setLeaveHash] = useState<string | null>(null);
  const guard = useRef({ dirty: false, busy: false, enabled: true });
  useLayoutEffect(() => {
    const currentUrl = window.location.href;
    const protectedDraft = () =>
      guard.current.enabled && (guard.current.dirty || guard.current.busy);
    const keepDraft = (event: HashChangeEvent | PopStateEvent) => {
      if (!protectedDraft() || window.location.href === currentUrl) return;
      const destination = window.location.hash;
      event.stopImmediatePropagation();
      window.history.replaceState(window.history.state, "", currentUrl);
      if (!guard.current.busy) {
        setLeaveHash(destination);
        setDiscard(true);
      }
    };
    const warn = (event: BeforeUnloadEvent) => {
      if (protectedDraft()) {
        event.preventDefault();
        event.returnValue = "Unsaved changes";
      }
    };
    window.addEventListener("beforeunload", warn);
    window.addEventListener("popstate", keepDraft, true);
    window.addEventListener("hashchange", keepDraft, true);
    return () => {
      window.removeEventListener("beforeunload", warn);
      window.removeEventListener("popstate", keepDraft, true);
      window.removeEventListener("hashchange", keepDraft, true);
    };
  }, []);
  const sourceReview = !!sourceDraft && isSourceDraft(sourceDraft);
  function requestClose() {
    if (guard.current.busy) return;
    if (guard.current.dirty) {
      setLeaveHash(null);
      setDiscard(true);
    } else onClose();
  }
  function changeQuiz(next: AdminLesson["quiz"]) {
    if (guard.current.busy) return;
    guard.current.dirty = true;
    setQuiz(next);
  }
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (guard.current.busy) return;
    const f = new FormData(event.currentTarget);
    guard.current.busy = true;
    setBusy(true);
    setError("");
    try {
      await api(
        sourceDraft ? `/admin/lessons/${sourceDraft.id}` : "/admin/lessons",
        {
          title: f.get("title"),
          category: f.get("category"),
          summary: f.get("summary"),
          body: f.get("body"),
          week: Number(f.get("week")),
          source_url: f.get("source_url"),
          source_title: f.get("source_title"),
          track: f.get("track"),
          level: f.get("level"),
          learning_objective: f.get("learning_objective"),
          exercise: f.get("exercise"),
          reflection_prompt: f.get("reflection_prompt"),
          source_note: f.get("source_note"),
          content_version: Number(f.get("content_version")),
          quiz,
        },
        sourceDraft ? "PATCH" : "POST",
      );
      guard.current.dirty = false;
      guard.current.enabled = false;
      refresh();
      notify(
        sourceDraft
          ? "Der bestehende Entwurf ist redaktionell gespeichert. Die Veröffentlichung bleibt ein eigener Schritt."
          : "Die Lektion ist als unveröffentlichter Entwurf gespeichert.",
      );
      onClose();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      guard.current.busy = false;
      setBusy(false);
    }
  }
  return (
    <>
      <Modal
        title={
          sourceDraft
            ? "Diesen Entwurf redigieren."
            : "Ein neuer Impuls darf wachsen."
        }
        description={
          sourceDraft
            ? "Du bearbeitest denselben Entwurf. Ein redaktionelles Speichern veröffentlicht ihn noch nicht."
            : "Die Lektion bleibt als Entwurf gespeichert, bis du sie bewusst freigibst."
        }
        onClose={requestClose}
        wide
      >
        <form
          className="form-grid"
          onSubmit={submit}
          onChange={() => {
            guard.current.dirty = true;
          }}
        >
          {sourceReview && (
            <div className="alert full">
              <Icon name="shield" />
              <p>
                Dies ist ein ungeprüfter Quellenfund. Prüfe das Original und
                ersetze Recherchetext und Recherche-Titel durch eine eigene
                fachlich eingeordnete Lektion mit passendem Verständnischeck.
                Die Quelle bleibt nachvollziehbar; es wird kein Duplikat
                angelegt.
              </p>
            </div>
          )}
          <label className="full">
            Titel
            <input
              name="title"
              required
              maxLength={160}
              readOnly={busy}
              defaultValue={sourceDraft?.title || ""}
            />
          </label>
          <label>
            Kategorie
            <input
              name="category"
              required
              maxLength={60}
              readOnly={busy}
              defaultValue={sourceDraft?.category || "Astrologische Reflexion"}
            />
          </label>
          <label>
            Position in der Bibliothek
            <input
              name="week"
              type="number"
              min="1"
              max="260"
              required
              readOnly={busy}
              defaultValue={sourceDraft?.week || nextWeek}
            />
          </label>
          <label>
            Themenraum
            <input
              name="track"
              maxLength={80}
              readOnly={busy}
              defaultValue={sourceDraft?.track || ""}
            />
          </label>
          <label>
            Niveau
            <select
              name="level"
              defaultValue={sourceDraft?.level || "foundation"}
              disabled={busy}
            >
              <option value="foundation">Grundlagen</option>
              <option value="deepening">Vertiefung</option>
              <option value="practice">Praxis</option>
            </select>
          </label>
          <label className="full">
            Kurze Einordnung
            <textarea
              name="summary"
              rows={3}
              required
              maxLength={600}
              readOnly={busy}
              defaultValue={sourceDraft?.summary || ""}
            />
          </label>
          <label className="full">
            Lernziel
            <textarea
              name="learning_objective"
              rows={2}
              maxLength={1000}
              readOnly={busy}
              defaultValue={sourceDraft?.learning_objective || ""}
            />
          </label>
          <label className="full">
            Lektionsinhalt
            <textarea
              name="body"
              rows={12}
              required
              maxLength={16000}
              readOnly={busy}
              defaultValue={sourceDraft?.body || ""}
              placeholder="Ein eigener zusammenhängender Lerntext mit klarer Quellenzuordnung und spiritueller Einordnung …"
            />
          </label>
          <label className="full">
            Übung
            <textarea
              name="exercise"
              rows={5}
              maxLength={3000}
              readOnly={busy}
              defaultValue={sourceDraft?.exercise || ""}
            />
          </label>
          <label className="full">
            Reflexionsfrage
            <textarea
              name="reflection_prompt"
              rows={3}
              maxLength={1000}
              readOnly={busy}
              defaultValue={sourceDraft?.reflection_prompt || ""}
            />
          </label>
          <label>
            Quellentitel
            <input
              name="source_title"
              required
              maxLength={200}
              readOnly={busy}
              defaultValue={sourceDraft?.source_title || ""}
            />
          </label>
          <label>
            Öffentliche Quellen-URL
            <input
              name="source_url"
              type="url"
              pattern="https://.*"
              maxLength={2048}
              required
              readOnly={busy}
              defaultValue={sourceDraft?.source_url || ""}
              placeholder="https://…"
            />
          </label>
          <label className="full">
            Quelle und inhaltliche Grenzen
            <textarea
              name="source_note"
              rows={5}
              maxLength={2000}
              readOnly={busy}
              defaultValue={sourceDraft?.source_note || ""}
            />
          </label>
          <label>
            Inhaltsversion
            <input
              name="content_version"
              type="number"
              min="1"
              max="100000"
              required
              readOnly={busy}
              defaultValue={sourceDraft?.content_version || 1}
            />
          </label>
          <div className="form-subtitle full">
            <Icon name="book" size={18} />
            <h3>Freiwilliger Verständnischeck · {quiz.length} Fragen</h3>
          </div>
          {quiz.map((question, questionIndex) => (
            <fieldset
              className="full"
              key={question.id}
              style={{
                border: "1px solid var(--border)",
                borderRadius: 12,
                padding: 18,
                margin: 0,
                minWidth: 0,
                display: "grid",
                gap: 14,
              }}
            >
              <legend>Frage {questionIndex + 1}</legend>
              <label>
                Quizfrage
                <input
                  value={question.question}
                  required
                  maxLength={400}
                  readOnly={busy}
                  onChange={(event) =>
                    changeQuiz(
                      quiz.map((item, index) =>
                        index === questionIndex
                          ? { ...item, question: event.target.value }
                          : item,
                      ),
                    )
                  }
                />
              </label>
              {question.options.map((option, optionIndex) => (
                <label key={optionIndex}>
                  Antwort {optionIndex + 1}
                  <input
                    value={option}
                    required
                    maxLength={300}
                    readOnly={busy}
                    onChange={(event) =>
                      changeQuiz(
                        quiz.map((item, index) =>
                          index === questionIndex
                            ? {
                                ...item,
                                options: item.options.map((value, index) =>
                                  index === optionIndex
                                    ? event.target.value
                                    : value,
                                ),
                              }
                            : item,
                        ),
                      )
                    }
                  />
                </label>
              ))}
              <label>
                Korrekte Antwort
                <select
                  value={question.correct_index}
                  disabled={busy}
                  onChange={(event) =>
                    changeQuiz(
                      quiz.map((item, index) =>
                        index === questionIndex
                          ? {
                              ...item,
                              correct_index: Number(event.target.value),
                            }
                          : item,
                      ),
                    )
                  }
                >
                  {question.options.map((_, index) => (
                    <option value={index} key={index}>
                      Antwort {index + 1}
                    </option>
                  ))}
                </select>
              </label>
              <div className="button-pair">
                <button
                  type="button"
                  className="button secondary small"
                  disabled={busy || question.options.length >= 8}
                  onClick={() =>
                    changeQuiz(
                      quiz.map((item, index) =>
                        index === questionIndex
                          ? { ...item, options: [...item.options, ""] }
                          : item,
                      ),
                    )
                  }
                >
                  Antwort ergänzen
                </button>
                <button
                  type="button"
                  className="button text small"
                  disabled={busy || question.options.length <= 2}
                  onClick={() =>
                    changeQuiz(
                      quiz.map((item, index) =>
                        index === questionIndex
                          ? {
                              ...item,
                              options: item.options.slice(0, -1),
                              correct_index: Math.min(
                                item.correct_index,
                                item.options.length - 2,
                              ),
                            }
                          : item,
                      ),
                    )
                  }
                >
                  Letzte Antwort entfernen
                </button>
                <button
                  type="button"
                  className="button text small"
                  disabled={busy || quiz.length <= 1}
                  onClick={() =>
                    changeQuiz(
                      quiz.filter((_, index) => index !== questionIndex),
                    )
                  }
                >
                  Frage entfernen
                </button>
              </div>
            </fieldset>
          ))}
          <div className="full">
            <button
              type="button"
              className="button secondary"
              disabled={busy || quiz.length >= 20}
              onClick={() =>
                changeQuiz([
                  ...quiz,
                  {
                    id: "q-" + crypto.randomUUID(),
                    question: "",
                    options: ["", ""],
                    correct_index: 0,
                  },
                ])
              }
            >
              <Icon name="plus" size={16} />
              Frage ergänzen
            </button>
          </div>
          {sourceReview && (
            <label className="checkbox-label full">
              <input type="checkbox" required disabled={busy} />
              <span>
                Ich habe das Original und seine Grenzen geprüft und den
                Rechercheentwurf eigenständig redigiert.
              </span>
            </label>
          )}
          <div className="full">
            <ErrorBox error={error} />
            {busy && (
              <p role="status">
                Wird gespeichert – die Eingaben sind kurz schreibgeschützt.
              </p>
            )}
          </div>
          <div className="form-actions full">
            <button
              type="button"
              className="button text"
              disabled={busy}
              onClick={requestClose}
            >
              Abbrechen
            </button>
            <button disabled={busy} className="button primary purple-button">
              {busy
                ? "Wird gespeichert …"
                : sourceDraft
                  ? "Redaktionell als Entwurf speichern"
                  : "Als Entwurf speichern"}
              <Icon name="note" size={17} />
            </button>
          </div>
        </form>
      </Modal>
      {discard && (
        <Modal
          title="Deine Änderungen sind noch nicht gespeichert."
          onClose={() => {
            setDiscard(false);
            setLeaveHash(null);
          }}
        >
          <p>
            Bearbeite den Entwurf weiter oder verwirf nur deine ungespeicherten
            Änderungen. Der gespeicherte Entwurf bleibt erhalten.
          </p>
          <div className="form-actions">
            <button
              className="button secondary"
              onClick={() => {
                setDiscard(false);
                setLeaveHash(null);
              }}
            >
              Weiter bearbeiten
            </button>
            <button
              className="button primary"
              onClick={() => {
                guard.current.enabled = false;
                onClose();
                if (leaveHash !== null) window.location.hash = leaveHash;
              }}
            >
              Änderungen verwerfen
            </button>
          </div>
        </Modal>
      )}
    </>
  );
}
