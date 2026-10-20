import {
  useEffect,
  useRef,
  useState,
  type FormEvent,
  type ReactNode,
} from "react";
import { api, dateFormat } from "./api";
import { useData, useRequestScope } from "./hooks";
import type { PageProps } from "./App";
import type {
  AcademyCourse,
  AcademyAttempt,
  AcademyLesson,
  AcademyOverview,
  AcademyQuizResult,
  AcademyRelease,
  Lesson,
} from "./types";
import { Badge, Empty, ErrorBox, Icon, Loading, Modal } from "./ui";
import {
  ACADEMY_LEVELS,
  LEARNING_PATHS,
  dueReviews,
  filterCourses,
  learningStage,
  quizReady,
} from "./academyModel";

type AcademyProps = PageProps & {
  onCreateNote: (lesson: Lesson) => void;
  onLessonUpdated: (lesson: Lesson) => void;
};

export function Academy(props: AcademyProps) {
  const overview = useData<AcademyOverview>("/academy", props.revision);
  const [course, setCourse] = useState<AcademyCourse | null>(null);
  const [selected, setSelected] = useState<number | null>(null);
  const [preview, setPreview] = useState(false);
  const [query, setQuery] = useState("");
  const [level, setLevel] = useState("");
  const [path, setPath] = useState("");
  if (!overview.data && overview.loading) return <Loading />;
  if (!overview.data) return <ErrorBox error={overview.error} />;
  const data = overview.data;
  const due = dueReviews(data.reviews);
  const count = data.courses.reduce((sum, item) => sum + item.lesson_count, 0);
  const published = data.courses.reduce(
    (sum, item) => sum + item.published_count,
    0,
  );
  const visible = filterCourses(data.courses, query, level, path);
  return (
    <section className="academy" aria-label="Lernakademie">
      <div className="academy-intro glass-card">
        <div>
          <span className="eyebrow">DEINE FREI WÄHLBARE AKADEMIE</span>
          <h2>
            Wissen verstehen.
            <br />
            <em>Deinen eigenen Weg finden.</em>
          </h2>
          <p>
            {data.courses.length} {data.courses.length === 1 ? "Kurs" : "Kurse"}{" "}
            · {count} Lektionen · {published} veröffentlicht. Du entscheidest
            über Thema, Niveau und Reihenfolge. Jeder veröffentlichte Inhalt ist
            direkt offen.
          </p>
          <p className="fineprint">
            Von westlicher Astrologie bis Jyotish, von Deutung bis
            Gesprächspraxis. Die jeweiligen Schulen und spirituellen Annahmen
            sind gekennzeichnet.
          </p>
        </div>
        <div className="academy-progress" aria-label="Dein Lernstand">
          <span className="academy-points">
            <strong>{data.progress.points}</strong> Lernpunkte
          </span>
          <span className="small-label">
            {learningStage(data.progress.points)}
          </span>
          <dl>
            <div>
              <dt>Gelesen</dt>
              <dd>{data.progress.read_count}</dd>
            </div>
            <div>
              <dt>Wissenschecks bestanden</dt>
              <dd>{data.progress.passed_count}</dd>
            </div>
            <div>
              <dt>Praxis selbst geprüft</dt>
              <dd>{data.progress.practice_count}</dd>
            </div>
          </dl>
          <details>
            <summary>Wie zählen die Punkte?</summary>
            <p>
              Pro Lektion einmalig: 5 fürs Lesen, 15 für einen bestandenen
              Wissenscheck und 20 für eine vollständig selbst geprüfte
              Praxisaufgabe. Wiederholen bleibt jederzeit möglich. Punkte und
              Lernabzeichen bestätigen Lernaktivität; sie sind keine
              Berufsqualifikation.
            </p>
          </details>
        </div>
      </div>
      <ErrorBox error={overview.error} />
      <section className="academy-paths" aria-label="Empfohlene Lernwege">
        <div className="workspace-section-heading">
          <div>
            <h3>Was möchtest du gerade lernen?</h3>
            <p>
              Lernwege sortieren passende Kurse für dich. Du kannst jederzeit
              wechseln.
            </p>
          </div>
          {path && (
            <button className="button text" onClick={() => setPath("")}>
              Alle Kurse zeigen
            </button>
          )}
        </div>
        <div className="academy-path-grid">
          {LEARNING_PATHS.map((item) => (
            <button
              key={item.id}
              className={"academy-path " + (path === item.id ? "selected" : "")}
              aria-pressed={path === item.id}
              onClick={() => {
                setPath(path === item.id ? "" : item.id);
                setLevel("");
                setCourse(null);
              }}
            >
              <Icon
                name={
                  item.id === "start"
                    ? "book"
                    : item.id === "deepen"
                      ? "orbit"
                      : "users"
                }
                size={22}
              />
              <strong>{item.title}</strong>
              <span>{item.description}</span>
            </button>
          ))}
        </div>
      </section>
      <div className="academy-tools">
        <label>
          Thema suchen
          <input
            type="search"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Zum Beispiel Transite oder Häuser"
          />
        </label>
        <label>
          Niveau
          <select
            value={level}
            onChange={(event) => setLevel(event.target.value)}
          >
            <option value="">Alle Niveaus</option>
            {Object.entries(ACADEMY_LEVELS).map(([key, name]) => (
              <option value={key} key={key}>
                {name}
              </option>
            ))}
          </select>
        </label>
        {data.preview_available && (
          <label className="academy-check">
            <input
              type="checkbox"
              checked={preview}
              onChange={(event) => {
                setPreview(event.target.checked);
                setCourse(null);
                setSelected(null);
              }}
            />
            Redaktionelle Vorschau
          </label>
        )}
      </div>
      {preview && (
        <div className="alert">
          <Icon name="eye" />
          <span>
            Redaktionelle Vorschau: Entwürfe lesen und Quellen prüfen.
            Lernpunkte, Aufgabenabgaben und persönliche Markierungen sind hier
            deaktiviert.
          </span>
        </div>
      )}
      {course ? (
        <AcademyCourseView
          key={`${course.id}-${preview}`}
          course={course}
          preview={preview}
          revision={props.revision}
          onBack={() => setCourse(null)}
          onOpen={setSelected}
        />
      ) : (
        <>
          <div className="workspace-section-heading">
            <h3>
              {path
                ? LEARNING_PATHS.find((item) => item.id === path)?.title
                : "Alle Kurse"}
            </h3>
            <span>
              {visible.length} {visible.length === 1 ? "Kurs" : "Kurse"}
            </span>
          </div>
          <div className="academy-course-grid">
            {visible.map((item) => (
              <article className="academy-course glass-card" key={item.id}>
                <div className="academy-course-meta">
                  <span className="academy-course-number">
                    {String(data.courses.indexOf(item) + 1).padStart(2, "0")}
                  </span>
                  <Badge>{ACADEMY_LEVELS[item.level]}</Badge>
                </div>
                <h3>{item.title}</h3>
                <p>{item.summary}</p>
                <span className="academy-tradition">{item.tradition}</span>
                <div className="academy-course-bottom">
                  <p>
                    {item.published_count} von {item.lesson_count} Lektionen
                    offen
                    {item.badge_earned && (
                      <span className="academy-earned">
                        <Icon name="check" size={15} /> Lernabzeichen erreicht
                      </span>
                    )}
                  </p>
                  <progress
                    max={Math.max(item.lesson_count, 1)}
                    value={item.completed_count}
                    aria-label={`${item.title}: ${item.completed_count} von ${item.lesson_count} gelesen`}
                  />
                  <div className="academy-course-footer">
                    <small>
                      {item.completed_count} gelesen · {item.passed_count}{" "}
                      Checks
                    </small>
                    <button
                      className="button secondary"
                      onClick={() => setCourse(item)}
                      aria-label={`${item.title} öffnen`}
                    >
                      {item.published_count || preview
                        ? "Kurs öffnen"
                        : "Kurs ansehen"}
                      <Icon name="arrow" size={16} />
                    </button>
                  </div>
                </div>
              </article>
            ))}
          </div>
          {!visible.length && (
            <Empty
              title="Kein Kurs passt zu dieser Auswahl."
              action={
                <button
                  className="button secondary"
                  onClick={() => {
                    setQuery("");
                    setLevel("");
                    setPath("");
                  }}
                >
                  Auswahl zurücksetzen
                </button>
              }
            >
              Versuche ein anderes Thema oder zeige alle Kurse.
            </Empty>
          )}
        </>
      )}
      <div className="academy-personal-grid">
        <section className="glass-card academy-personal">
          <div className="workspace-section-heading">
            <h3>Wieder aufnehmen</h3>
            <Badge>{due.length} fällig</Badge>
          </div>
          <p>
            Ein kurzer Wissenscheck hilft beim Wiederholen. Auch künftige
            Wiederholungen sind schon offen.
          </p>
          {data.reviews.length ? (
            <ul className="academy-review-list">
              {data.reviews.map((item) => (
                <li key={item.lesson_id}>
                  <button onClick={() => setSelected(item.lesson_id)}>
                    <span>{item.title}</span>
                    <small>
                      {Date.parse(item.due_at) <= Date.now()
                        ? "Jetzt wiederholen"
                        : `Ab ${dateFormat(item.due_at)}`}
                    </small>
                    <Icon name="arrow" size={16} />
                  </button>
                </li>
              ))}
            </ul>
          ) : (
            <p className="academy-empty-hint">
              Nach deinem ersten Wissenscheck erscheint hier eine Wiederholung.
            </p>
          )}
        </section>
        <section className="glass-card academy-personal">
          <div className="workspace-section-heading">
            <h3>Deine Lernabzeichen</h3>
            <Badge>{data.badges.length}</Badge>
          </div>
          <p>
            Ein Kursabzeichen erhältst du, wenn du seine Wissenschecks bestehst
            und alle Praxisaufgaben anhand der Kriterien selbst prüfst.
          </p>
          {data.badges.length ? (
            <ul className="academy-badge-list">
              {data.badges.map((badge) => (
                <li key={badge.id}>
                  <span className="card-icon crown">
                    <Icon name="spark" />
                  </span>
                  <div>
                    <strong>{badge.title}</strong>
                    <small>Erreicht am {dateFormat(badge.earned_at)}</small>
                  </div>
                </li>
              ))}
            </ul>
          ) : (
            <p className="academy-empty-hint">
              Dein erstes Abzeichen darf wachsen. Es gibt keinen Zeitdruck.
            </p>
          )}
        </section>
      </div>
      {props.user.role === "admin" && (
        <AcademyReleasePanel
          revision={props.revision}
          onReleased={props.refresh}
        />
      )}
      {selected !== null && (
        <AcademyLessonReader
          key={`${selected}-${preview}`}
          {...props}
          id={selected}
          preview={preview}
          onClose={() => setSelected(null)}
          onCreateNote={(lesson) => {
            setSelected(null);
            props.onCreateNote(lesson);
          }}
          onUpdated={props.onLessonUpdated}
        />
      )}
    </section>
  );
}

function AcademyCourseView({
  course,
  preview,
  revision,
  onBack,
  onOpen,
}: {
  course: AcademyCourse;
  preview: boolean;
  revision: number;
  onBack: () => void;
  onOpen: (id: number) => void;
}) {
  const { data, loading, error } = useData<{
    course: AcademyCourse;
    lessons: Lesson[];
  }>(
    `/academy/courses/${encodeURIComponent(course.id)}${preview ? "?preview=1" : ""}`,
    revision,
  );
  return (
    <section className="academy-course-view">
      <button className="button text" onClick={onBack}>
        <Icon name="chevron" size={16} className="academy-back" />
        Zur Kursübersicht
      </button>
      <div className="academy-course-heading">
        <span className="eyebrow">{course.tradition}</span>
        <h2>{course.title}</h2>
        <p>{course.summary}</p>
        <Badge>{ACADEMY_LEVELS[course.level]}</Badge>
      </div>
      <ErrorBox error={error} />
      {loading && !data ? (
        <Loading />
      ) : data?.lessons.length ? (
        <ol className="academy-lessons">
          {data.lessons.map((lesson, index) => (
            <li key={lesson.id}>
              <button onClick={() => onOpen(lesson.id)}>
                <span className="academy-lesson-index">
                  {String(index + 1).padStart(2, "0")}
                </span>
                <span className="academy-lesson-caption">
                  <strong>{lesson.title}</strong>
                  <span>{lesson.summary}</span>
                  <small>
                    {ACADEMY_LEVELS[lesson.level]}
                    {lesson.minutes ? ` · ca. ${lesson.minutes} Min.` : ""}
                    {lesson.completed ? " · Gelesen" : ""}
                    {lesson.status === "draft" ? " · Entwurf" : ""}
                  </small>
                </span>
                <Icon name="arrow" size={19} />
              </button>
            </li>
          ))}
        </ol>
      ) : (
        !error && (
          <Empty title="Dieser Kurs wird redaktionell geprüft.">
            Die Lektionen werden nach der bewussten Inhaltsfreigabe geöffnet.
            Andere veröffentlichte Kurse kannst du frei wählen.
          </Empty>
        )
      )}
    </section>
  );
}

function inlineText(value: string): ReactNode[] {
  return value
    .split(/(\*\*[^*]+\*\*)/g)
    .map((part, index) =>
      part.startsWith("**") && part.endsWith("**") ? (
        <strong key={index}>{part.slice(2, -2)}</strong>
      ) : (
        part
      ),
    );
}
export function TeachingText({ body }: { body: string }) {
  return (
    <div className="academy-prose">
      {body
        .split(/\n\s*\n/)
        .filter(Boolean)
        .map((block, index) => {
          const lines = block.trim().split("\n");
          if (/^#{1,4}\s/.test(lines[0])) {
            const [heading, ...rest] = lines;
            return (
              <div key={index}>
                <h3>{inlineText(heading.replace(/^#{1,4}\s+/, ""))}</h3>
                {rest.length > 0 && <p>{inlineText(rest.join(" "))}</p>}
              </div>
            );
          }
          if (lines.every((line) => /^[-*]\s/.test(line)))
            return (
              <ul key={index}>
                {lines.map((line, n) => (
                  <li key={n}>{inlineText(line.replace(/^[-*]\s+/, ""))}</li>
                ))}
              </ul>
            );
          if (lines.every((line) => /^\d+\.\s/.test(line)))
            return (
              <ol key={index}>
                {lines.map((line, n) => (
                  <li key={n}>{inlineText(line.replace(/^\d+\.\s+/, ""))}</li>
                ))}
              </ol>
            );
          return <p key={index}>{inlineText(block)}</p>;
        })}
    </div>
  );
}

type ReaderProps = PageProps & {
  id: number;
  preview?: boolean;
  onClose: () => void;
  onCreateNote: (lesson: Lesson) => void;
  onUpdated: (lesson: Lesson) => void;
};
export function AcademyLessonReader(props: ReaderProps) {
  const [dirty, setDirty] = useState(false);
  const [saving, setSaving] = useState(false);
  const [leaveQuestion, setLeaveQuestion] = useState(false);
  const leaveAction = useRef<() => void>(props.onClose);
  useEffect(() => {
    if (!dirty) return;
    const warn = (event: BeforeUnloadEvent) => {
      event.preventDefault();
      event.returnValue = "";
    };
    window.addEventListener("beforeunload", warn);
    return () => window.removeEventListener("beforeunload", warn);
  }, [dirty]);
  function leave(action: () => void) {
    if (saving) return;
    if (dirty) {
      leaveAction.current = action;
      setLeaveQuestion(true);
    } else action();
  }
  const { data, setData, loading, error } = useData<AcademyLesson>(
    `/academy/lessons/${props.id}${props.preview ? "?preview=1" : ""}`,
  );
  return (
    <Modal
      title={data?.lesson.title || "Lektion öffnen"}
      description={data ? data.course.title : undefined}
      wide
      onClose={() => leave(props.onClose)}
    >
      {!data && loading ? (
        <Loading />
      ) : !data ? (
        <ErrorBox error={error} />
      ) : (
        <AcademyLessonContent
          key={props.id}
          {...props}
          data={data}
          setData={setData}
          onDirtyChange={setDirty}
          onBusyChange={setSaving}
          onCreateNote={(lesson) => leave(() => props.onCreateNote(lesson))}
        />
      )}
      {leaveQuestion && (
        <Modal
          title="Bearbeitung noch nicht gespeichert"
          description="Deine Änderungen an der Praxisaufgabe sind noch offen."
          onClose={() => setLeaveQuestion(false)}
        >
          <p>
            Kehre zur Lektion zurück und speichere deine Bearbeitung, um sie
            später wieder aufzunehmen.
          </p>
          <div className="form-actions">
            <button
              className="button secondary"
              onClick={() => setLeaveQuestion(false)}
            >
              Weiterarbeiten
            </button>
            <button
              className="button text"
              onClick={() => {
                setDirty(false);
                setLeaveQuestion(false);
                leaveAction.current();
              }}
            >
              Änderungen verwerfen
            </button>
          </div>
        </Modal>
      )}
    </Modal>
  );
}

function AcademyLessonContent({
  data,
  setData,
  onDirtyChange,
  onBusyChange,
  ...props
}: ReaderProps & {
  data: AcademyLesson;
  setData: (data: AcademyLesson) => void;
  onDirtyChange: (dirty: boolean) => void;
  onBusyChange: (busy: boolean) => void;
}) {
  const isCurrent = useRequestScope();
  const [section, setSection] = useState("teaching");
  const [answers, setAnswers] = useState<Record<string, number>>({});
  const latestPractice = data.latest_practice;
  const [history, setHistory] = useState(data.attempts);
  const [historyMore, setHistoryMore] = useState(data.attempts_has_more);
  const [historyBusy, setHistoryBusy] = useState(false);
  const historyLock = useRef(false);
  const historyVersion = useRef(0);
  useEffect(() => {
    historyVersion.current += 1;
    setHistory(data.attempts);
    setHistoryMore(data.attempts_has_more);
  }, [data.attempts, data.attempts_has_more]);
  const [response, setResponse] = useState(latestPractice?.response || "");
  const [checks, setChecks] = useState<boolean[]>(
    data.practice.rubric.map(
      (_, index) => latestPractice?.self_checks?.[index] || false,
    ),
  );
  const [result, setResult] = useState<AcademyQuizResult | null>(null);
  const [busy, setBusy] = useState("");
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const lock = useRef(false);
  const preview = Boolean(props.preview);
  const lesson = data.lesson;
  async function olderAttempts() {
    if (historyLock.current || !historyMore || !history.length) return;
    historyLock.current = true;
    setHistoryBusy(true);
    setError("");
    const cursor = history[history.length - 1].id;
    const version = historyVersion.current;
    try {
      const page = await api<{ items: AcademyAttempt[]; has_more: boolean }>(
        `/academy/lessons/${lesson.id}/attempts?before_id=${encodeURIComponent(cursor)}${preview ? "&preview=true" : ""}`,
      );
      if (isCurrent() && version === historyVersion.current) {
        setHistory((current) => [...current, ...page.items.filter((item) => !current.some((old) => old.id === item.id))]);
        setHistoryMore(page.has_more);
      }
    } catch (e) {
      if (isCurrent()) setError((e as Error).message);
    } finally {
      historyLock.current = false;
      if (isCurrent()) setHistoryBusy(false);
    }
  }
  async function run(action: string, task: () => Promise<string>) {
    if (lock.current || preview) return;
    lock.current = true;
    setBusy(action);
    onBusyChange(true);
    setError("");
    setMessage("");
    try {
      const feedback = await task();
      const refreshed = await api<AcademyLesson>(
        `/academy/lessons/${lesson.id}`,
      );
      if (isCurrent()) {
        setData(refreshed);
        setMessage(feedback);
        props.onUpdated(refreshed.lesson);
      }
    } catch (e) {
      if (isCurrent()) setError((e as Error).message);
    } finally {
      lock.current = false;
      if (isCurrent()) {
        setBusy("");
        onBusyChange(false);
      }
    }
  }
  function mark(field: "bookmarked" | "pinned") {
    void run(field, async () => {
      const updated = await api<Lesson>(
        `/learning/${lesson.id}/state`,
        { [field]: !lesson[field] },
        "PATCH",
      );
      return field === "bookmarked"
        ? updated.bookmarked
          ? "Lesezeichen gespeichert."
          : "Lesezeichen entfernt."
        : updated.pinned
          ? "Auf deiner Pinnwand gespeichert."
          : "Von deiner Pinnwand entfernt.";
    });
  }
  function complete() {
    void run("complete", async () => {
      const saved = await api<{ points_awarded: number }>(
        `/academy/lessons/${lesson.id}/complete`,
        {},
      );
      return `Als gelesen gespeichert.${saved.points_awarded ? ` +${saved.points_awarded} Lernpunkte.` : " Deine Punkte wurden bereits gezählt."}`;
    });
  }
  function quiz(event: FormEvent) {
    event.preventDefault();
    if (!quizReady(data.quiz, answers)) {
      setError("Bitte beantworte jede Frage, bevor du den Check auswertest.");
      return;
    }
    void run("quiz", async () => {
      const saved = await api<AcademyQuizResult>(
        `/academy/lessons/${lesson.id}/quiz`,
        { answers },
      );
      if (isCurrent()) setResult(saved);
      return saved.passed
        ? `Wissenscheck bestanden.${saved.points_awarded ? ` +${saved.points_awarded} Lernpunkte.` : " Bereits erworbene Punkte bleiben erhalten."}`
        : "Dein Feedback ist da. Du kannst die Erklärungen lesen und jederzeit erneut üben.";
    });
  }
  function practice(event: FormEvent) {
    event.preventDefault();
    void run("practice", async () => {
      const saved = await api<{ points_awarded: number }>(
        `/academy/lessons/${lesson.id}/practice`,
        { response: response.trim(), self_checks: checks },
      );
      if (isCurrent()) onDirtyChange(false);
      return `Deine Bearbeitung und Selbstprüfung sind gespeichert.${saved.points_awarded ? ` +${saved.points_awarded} Lernpunkte.` : checks.every(Boolean) ? " Bereits erworbene Punkte bleiben erhalten." : " Offene Kriterien kannst du später überarbeiten."}`;
    });
  }
  return (
    <div className="academy-reader">
      {preview && (
        <div className="alert">
          <Icon name="eye" />
          <span>
            Redaktionelle Vorschau ·{" "}
            {lesson.status === "draft" ? "unveröffentlicht" : "veröffentlicht"}.
            Hier werden keine Lernaktivitäten gespeichert.
          </span>
        </div>
      )}
      <div className="academy-reader-meta">
        <Badge>{ACADEMY_LEVELS[lesson.level]}</Badge>
        <Badge>{data.state.read ? "Gelesen" : "Noch nicht gelesen"}</Badge>
        <Badge>
          {data.state.quiz_passed
            ? "Wissenscheck bestanden"
            : "Wissenscheck offen"}
        </Badge>
        <Badge>
          {data.state.practice_completed
            ? "Praxis selbst geprüft"
            : "Praxis offen"}
        </Badge>
      </div>
      <div className="workspace-reader-actions">
        <button
          className="button secondary"
          disabled={preview || !!busy}
          aria-pressed={lesson.bookmarked}
          onClick={() => mark("bookmarked")}
        >
          <Icon name="heart" size={17} />
          {lesson.bookmarked ? "Gemerkt" : "Merken"}
        </button>
        <button
          className="button secondary"
          disabled={preview || !!busy}
          aria-pressed={lesson.pinned}
          onClick={() => mark("pinned")}
        >
          <Icon name="task" size={17} />
          {lesson.pinned ? "Gepinnt" : "Pinnen"}
        </button>
        <button
          className="button secondary"
          disabled={preview || !!busy}
          onClick={() => props.onCreateNote(lesson)}
        >
          <Icon name="note" size={17} />
          Eigene Notiz
        </button>
      </div>
      <section className="workspace-reader-goal">
        <span className="small-label">DEIN LERNZIEL</span>
        <p>{lesson.learning_objective}</p>
      </section>
      <nav className="academy-reader-nav" aria-label="Abschnitte der Lektion">
        {[
          { id: "teaching", label: "Lehrtext & Beispiele" },
          { id: "practice", label: "Praxisaufgabe" },
          { id: "quiz", label: "Wissenscheck" },
          { id: "sources", label: "Quellen & Verlauf" },
        ].map((item) => (
          <button
            key={item.id}
            className={section === item.id ? "active" : ""}
            aria-current={section === item.id ? "page" : undefined}
            onClick={() => {
              setSection(item.id);
              setError("");
            }}
          >
            {item.label}
          </button>
        ))}
      </nav>
      <ErrorBox error={error} />
      {message && (
        <p className="workspace-feedback" role="status">
          {message}
        </p>
      )}
      {section === "teaching" && (
        <section aria-label="Lehrtext und Beispiele">
          <TeachingText body={lesson.body} />
          <div className="academy-examples">
            {data.examples.map((example, index) => (
              <section key={index} className="academy-example">
                <span className="small-label">
                  EIGENES BEISPIEL {index + 1}
                </span>
                <h3>{example.title}</h3>
                <TeachingText body={example.body} />
              </section>
            ))}
          </div>
          <div className="academy-step-actions">
            <button
              className="button secondary"
              disabled={preview || !!busy || data.state.read}
              onClick={complete}
            >
              <Icon name={data.state.read ? "check" : "book"} size={17} />
              {data.state.read
                ? "Gelesen gespeichert"
                : busy === "complete"
                  ? "Wird gespeichert …"
                  : "Als gelesen markieren · 5 Punkte"}
            </button>
            <button
              className="button primary"
              onClick={() => setSection("practice")}
            >
              Zur Praxisaufgabe
              <Icon name="arrow" size={17} />
            </button>
          </div>
        </section>
      )}
      {section === "practice" && (
        <section aria-label="Praxisaufgabe">
          <h3>Jetzt machst du etwas Eigenes daraus.</h3>
          <TeachingText body={data.practice.prompt} />
          <form className="academy-practice-form" onSubmit={practice}>
            <label>
              Deine Bearbeitung
              <textarea
                rows={8}
                maxLength={12000}
                minLength={40}
                required
                readOnly={preview || !!busy}
                value={response}
                onChange={(event) => {
                  setResponse(event.target.value);
                  onDirtyChange(true);
                }}
                placeholder="Arbeite mit den fiktiven Angaben der Aufgabe. Verwende hier keine echten Klientendaten."
              />
              <small>
                {response.length} / 12.000 Zeichen · Mindestens 40 Zeichen.
                Gespeichert wird mit „Bearbeitung speichern“.
              </small>
            </label>
            <details className="academy-model-answer">
              <summary>Musterbearbeitung ansehen</summary>
              <p className="fineprint">
                Eine nachvollziehbare mögliche Bearbeitung. Bei offenen
                Deutungen können andere begründete Antworten genauso passend
                sein.
              </p>
              <TeachingText body={data.practice.model_answer} />
            </details>
            <fieldset className="academy-rubric">
              <legend>Deine Selbstprüfung</legend>
              <p>
                Vergleiche deine Bearbeitung mit den Kriterien. Setze nur
                Häkchen, die du selbst geprüft hast. Das ist keine automatische
                fachliche Bewertung.
              </p>
              {data.practice.rubric.map((criterion, index) => (
                <label className="academy-check" key={index}>
                  <input
                    type="checkbox"
                    disabled={preview || !!busy}
                    checked={checks[index]}
                    onChange={(event) => {
                      onDirtyChange(true);
                      setChecks((current) =>
                        current.map((value, n) =>
                          index === n ? event.target.checked : value,
                        ),
                      );
                    }}
                  />
                  <span>{criterion}</span>
                </label>
              ))}
            </fieldset>
            <div className="academy-step-actions">
              <button
                className="button primary"
                disabled={preview || !!busy || response.trim().length < 40}
              >
                {busy === "practice"
                  ? "Wird gespeichert …"
                  : "Bearbeitung speichern"}
                <Icon name="check" size={17} />
              </button>
              <button
                type="button"
                className="button secondary"
                onClick={() => setSection("quiz")}
              >
                Zum Wissenscheck
                <Icon name="arrow" size={17} />
              </button>
            </div>
            <p className="fineprint">
              Auch mit offenen Kriterien kannst du speichern. Für 20 einmalige
              Lernpunkte prüfst du alle Kriterien. Deine früheren Abgaben
              bleiben im Verlauf erhalten.
            </p>
          </form>
        </section>
      )}
      {section === "quiz" && (
        <section aria-label="Wissenscheck">
          <h3>Was ist hängen geblieben?</h3>
          <p>
            Der freiwillige Wissenscheck erklärt jede Antwort nach der Abgabe.
            Er sperrt keine Lektion. Ab 80 % gilt er als bestanden.
          </p>
          <form className="academy-quiz" onSubmit={quiz}>
            {data.quiz.map((question, index) => {
              const feedback = result?.feedback.find(
                (item) => item.question_id === question.id,
              );
              return (
                <fieldset key={question.id}>
                  <legend>
                    {index + 1}. {question.question}
                  </legend>
                  {question.options.map((option, optionIndex) => (
                    <label className="academy-check" key={optionIndex}>
                      <input
                        type="radio"
                        name={question.id}
                        checked={answers[question.id] === optionIndex}
                        disabled={preview || !!busy}
                        onChange={() => {
                          setAnswers((current) => ({
                            ...current,
                            [question.id]: optionIndex,
                          }));
                          setResult(null);
                        }}
                      />
                      <span>{option}</span>
                    </label>
                  ))}
                  {feedback && (
                    <div
                      className={
                        "academy-answer-feedback " +
                        (feedback.correct ? "correct" : "retry")
                      }
                    >
                      <strong>
                        {feedback.correct
                          ? "Richtig beantwortet"
                          : `Passende Antwort: ${question.options[feedback.correct_index]}`}
                      </strong>
                      <p>{feedback.explanation}</p>
                    </div>
                  )}
                </fieldset>
              );
            })}
            <button
              className="button primary"
              disabled={preview || !!busy || !quizReady(data.quiz, answers)}
            >
              {busy === "quiz" ? "Wird ausgewertet …" : "Antworten prüfen"}
              <Icon name="check" size={17} />
            </button>
          </form>
          {result && (
            <div className="academy-quiz-result" role="status">
              <strong>
                {result.score} % · {result.passed ? "Bestanden" : "Weiter üben"}
              </strong>
              <p>
                Nächste Wiederholung: {dateFormat(result.review_due_at)}. Du
                kannst den Check auch vorher wiederholen.
              </p>
            </div>
          )}
        </section>
      )}
      {section === "sources" && (
        <section aria-label="Quellen und eigener Verlauf">
          <h3>Quellen & Einordnung</h3>
          <p>
            Die Lehrtexte und Beispiele wurden für diese Akademie eigenständig
            ausgearbeitet. Die Quellen zeigen die jeweilige Tradition und
            Perspektive.
          </p>
          <ul className="academy-source-list">
            {data.sources.map((source, index) => (
              <li key={index}>
                <strong>{source.author}</strong>
                {/^https:\/\//.test(source.url) ? (
                  <a
                    href={source.url}
                    target="_blank"
                    rel="noopener noreferrer"
                  >
                    {source.title}
                    <Icon name="arrow" size={15} />
                  </a>
                ) : (
                  <span>{source.title}</span>
                )}
                <p>{source.note}</p>
                <small>Quelle geprüft: {source.checked_at}</small>
              </li>
            ))}
          </ul>
          <h3>Dein Aufgabenverlauf</h3>
          {history.length ? (
            <div className="academy-attempts">
              {history.map((attempt) => (
                <details key={attempt.id}>
                  <summary>
                    {attempt.kind === "practice"
                      ? "Praxisaufgabe"
                      : "Wissenscheck"}{" "}
                    ·{" "}
                    {dateFormat(attempt.created_at, {
                      day: "2-digit",
                      month: "short",
                      hour: "2-digit",
                      minute: "2-digit",
                    })}
                    {attempt.kind !== "practice" && attempt.score != null
                      ? ` · ${attempt.score} %`
                      : ""}
                  </summary>
                  {attempt.response ? (
                    <>
                      <p className="academy-attempt-response">
                        {attempt.response}
                      </p>
                      <p>
                        {attempt.self_checks?.filter(Boolean).length || 0} von{" "}
                        {data.practice.rubric.length} Kriterien selbst geprüft.
                      </p>
                    </>
                  ) : (
                    <>
                      <p>
                        {attempt.passed
                          ? "Wissenscheck bestanden."
                          : "Eine weitere Wiederholung kann helfen."}
                      </p>
                      {attempt.feedback?.map((feedback, index) => (
                        <div className="academy-answer-feedback" key={index}>
                          <strong>
                            {
                              data.quiz.find(
                                (question) =>
                                  question.id === feedback.question_id,
                              )?.question
                            }
                          </strong>
                          <p>
                            {feedback.correct
                              ? "Richtig beantwortet. "
                              : "Hier gab es noch eine Lücke. "}
                            {feedback.explanation}
                          </p>
                        </div>
                      ))}
                    </>
                  )}
                </details>
              ))}
              {historyMore && (
                <button className="button secondary" disabled={historyBusy} onClick={() => void olderAttempts()}>
                  {historyBusy ? "Verlauf wird geladen…" : "Ältere Bearbeitungen laden"}
                </button>
              )}
            </div>
          ) : (
            <p className="academy-empty-hint">
              Deine gespeicherten Aufgaben erscheinen hier.
            </p>
          )}
        </section>
      )}
    </div>
  );
}

function AcademyReleasePanel({
  revision,
  onReleased,
}: {
  revision: number;
  onReleased: () => void;
}) {
  const release = useData<AcademyRelease>("/admin/academy/release", revision);
  const [confirm, setConfirm] = useState<AcademyRelease | null>(null);
  const [acknowledged, setAcknowledged] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const lock = useRef(false);
  async function publish() {
    if (!confirm || !acknowledged || lock.current) return;
    lock.current = true;
    setBusy(true);
    setError("");
    try {
      await api<AcademyRelease>("/admin/academy/release", {
        manifest_sha256: confirm.manifest_sha256,
        acknowledged: true,
      });
      setConfirm(null);
      setAcknowledged(false);
      onReleased();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      lock.current = false;
      setBusy(false);
    }
  }
  return (
    <section className="glass-card academy-release">
      <span className="eyebrow">REDAKTION · NUR FÜR BETREIBER</span>
      <h3>Erstbestand gemeinsam freigeben</h3>
      <p>
        Neue Lehrinhalte bleiben Entwürfe, bis du das vollständige Paket geprüft
        hast. Zweiwöchentliche Ergänzungen brauchen weiterhin ihre eigene
        Freigabe.
      </p>
      <ErrorBox error={release.error} />
      {release.data && (
        <>
          <p>
            <strong>
              {release.data.lesson_count} / {release.data.expected_lessons}{" "}
              Lektionen
            </strong>{" "}
            in {release.data.course_count} Kursen · {release.data.draft_count}{" "}
            Entwürfe · {release.data.published_count} veröffentlicht
          </p>
          <button
            className="button secondary"
            disabled={!release.data.ready || release.data.draft_count === 0}
            onClick={() => {
              setConfirm(release.data);
              setAcknowledged(false);
              setError("");
            }}
          >
            {release.data.draft_count === 0 && release.data.lesson_count > 0
              ? "Erstbestand bereits veröffentlicht"
              : "Gesamtfreigabe prüfen"}
            <Icon name="shield" size={17} />
          </button>
          {!release.data.ready && (
            <small>
              Die Gesamtfreigabe ist erst für das vollständige, gültige Paket
              verfügbar.
            </small>
          )}
        </>
      )}
      {confirm && (
        <Modal
          title="120 Lektionen bewusst veröffentlichen?"
          description="Diese Freigabe öffnet den geprüften Erstbestand für die Beraterkonten."
          onClose={() => {
            if (!busy) setConfirm(null);
          }}
        >
          <p>
            {confirm.lesson_count} Lektionen in {confirm.course_count} Kursen.
            Prüfe Lehrtexte, Quellen, Musterbearbeitungen und Antwortfeedback in
            der redaktionellen Vorschau.
          </p>
          <p className="academy-release-hash">
            Paketkennung: <code>{confirm.manifest_sha256}</code>
          </p>
          <label className="academy-check">
            <input
              type="checkbox"
              checked={acknowledged}
              disabled={busy}
              onChange={(event) => setAcknowledged(event.target.checked)}
            />
            <span>
              Ich habe dieses konkrete Gesamtpaket inhaltlich geprüft und gebe
              es zur Veröffentlichung frei.
            </span>
          </label>
          <ErrorBox error={error} />
          <div className="form-actions">
            <button
              className="button text"
              disabled={busy}
              onClick={() => setConfirm(null)}
            >
              Zurück zur Prüfung
            </button>
            <button
              className="button primary"
              disabled={!acknowledged || busy}
              onClick={() => void publish()}
            >
              {busy
                ? "Wird veröffentlicht …"
                : "Geprüftes Paket veröffentlichen"}
            </button>
          </div>
        </Modal>
      )}
    </section>
  );
}
