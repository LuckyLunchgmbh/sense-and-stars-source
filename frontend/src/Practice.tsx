import { useRef, useState, type FormEvent } from "react";
import {
  api,
  dateFormat,
  money,
  nextAppointmentTime,
  toBerlinISO,
} from "./api";
import { go, useData, useRequestScope } from "./hooks";
import { clientMatchesWorkspace } from "./practiceMode";
import type {
  Appointment,
  Chart,
  Client,
  Dashboard,
  LearningData,
  Place,
  Portal,
  Resource,
} from "./types";
import type { PageProps } from "./App";
import {
  Avatar,
  Badge,
  Empty,
  ErrorBox,
  Icon,
  Loading,
  Modal,
  OrbitArt,
  SectionTitle,
  type IconName,
} from "./ui";
import { BodyChart } from "./BodyChart";
import { ContextHelp } from "./Help";
import { euroToCents, suggestedPrice } from "./pricing";
const modeQuery = (practice?: boolean) =>
  practice ? "?practice=1" : "?practice=0";
const statusName: Record<Appointment["status"], string> = {
  scheduled: "Geplant",
  in_progress: "In Sitzung",
  completed: "Abgeschlossen",
  cancelled: "Abgesagt",
};
const resourceName = { note: "Notiz", task: "Aufgabe", audio: "Audio-Impuls" };
const planetNames: Record<string, string> = {
  Sun: "Sonne",
  Moon: "Mond",
  Mercury: "Merkur",
  Venus: "Venus",
  Mars: "Mars",
  Jupiter: "Jupiter",
  Saturn: "Saturn",
  Uranus: "Uranus",
  Neptune: "Neptun",
  Pluto: "Pluto",
  TrueNode: "Mondknoten",
  mean_node: "Mondknoten",
  Chiron: "Chiron",
};
const zodiac = [
  "♈",
  "♉",
  "♊",
  "♋",
  "♌",
  "♍",
  "♎",
  "♏",
  "♐",
  "♑",
  "♒",
  "♓",
];
const planetSymbol: Record<string, string> = {
  Sun: "☉",
  Moon: "☽",
  Mercury: "☿",
  Venus: "♀",
  Mars: "♂",
  Jupiter: "♃",
  Saturn: "♄",
  Uranus: "♅",
  Neptune: "♆",
  Neptun: "♆",
  Pluto: "♇",
  Sonne: "☉",
  Mond: "☽",
  Merkur: "☿",
};
export function DashboardPage(props: PageProps) {
  const { data, loading, error } = useData<Dashboard>(
    "/dashboard" + modeQuery(props.practice),
    props.revision,
  );
  const learning = useData<LearningData>("/learning", props.revision);
  const [prepare, setPrepare] = useState<Appointment | null>(null);
  const first = props.user.name.split(" ")[0];
  if (loading && !data) return <Loading />;
  if (!data) return <ErrorBox error={error} />;
  const next = data.appointments
    .filter((a) => a.status === "scheduled" || a.status === "in_progress")
    .sort((a, b) => a.start_at.localeCompare(b.start_at));
  const lesson = learning.data?.lessons.find(
    (l) => l.available && !l.completed,
  );
  const hour = new Date().getHours();
  return (
    <>
      <div className="page-heading dashboard-heading">
        <div>
          <span className="eyebrow">
            {dateFormat(new Date().toISOString(), {
              weekday: "long",
              day: "numeric",
              month: "long",
              year: "numeric",
            }).toUpperCase()}
          </span>
          <h1>
            {hour < 11
              ? "Guten Morgen"
              : hour < 18
                ? "Schön, dass du da bist"
                : "Guten Abend"}
            , {first}.
          </h1>
          <p>Alles, was dich und deine Praxis heute verbindet.</p>
        </div>
        <button className="button secondary" onClick={() => go("calendar")}>
          <Icon name="plus" size={17} /> Termin planen
        </button>
      </div>
      <ErrorBox error={error} />
      <div className="dashboard-metrics">
        <Metric
          icon="users"
          tone="root"
          value={String(data.clients_count)}
          label="Menschen in Begleitung"
          detail="Deine Klienten"
        />
        <Metric
          icon="calendar"
          tone="sacral"
          value={String(data.upcoming_count)}
          label="Kommende Sitzungen"
          detail="Raum für Verbindung"
        />
        <Metric
          icon="chart"
          tone="solar"
          value={money(data.revenue_cents)}
          label="Sitzungswert"
          detail={`${data.completed_count} Sitzungen · kein Zahlungseingang`}
        />
      </div>
      <div className="dashboard-grid">
        <div className="dashboard-primary">
          <section className="connection-card">
            <div className="connection-copy">
              <span className="eyebrow">MIT PRÄSENZ BEGLEITEN</span>
              <h2>
                Raum für
                <br />
                <em>echte Verbindung.</em>
              </h2>
              <p>
                Jeder Mensch bringt seine eigene Geschichte.
                <br />
                Hier findet sie ihren Platz.
              </p>
              <button className="button light" onClick={() => go("clients")}>
                Zu deinen Klienten <Icon name="arrow" size={17} />
              </button>
            </div>
            <OrbitArt />
            <span className="connection-caption">
              IM EIGENEN RHYTHMUS ENTFALTEN
            </span>
          </section>
          <section className="glass-card appointments-card">
            <SectionTitle
              title="Deine nächsten Begegnungen"
              eyebrow="ZEIT FÜR VERBINDUNG"
            >
              <button className="text-link" onClick={() => go("calendar")}>
                Zum Kalender <Icon name="arrow" size={15} />
              </button>
            </SectionTitle>
            {next.length ? (
              next
                .slice(0, 3)
                .map((a) => (
                  <AppointmentRow
                    key={a.id}
                    appointment={a}
                    practice={props.practice}
                    onPrepare={() => setPrepare(a)}
                    compact
                  />
                ))
            ) : (
              <Empty icon="calendar" title="Ein freier Moment.">
                Plane eine neue Sitzung in deinem Kalender.
              </Empty>
            )}
          </section>
          <section className="glass-card clients-preview">
            <SectionTitle
              title="Menschen in deinem Raum"
              eyebrow="INDIVIDUELL BEGLEITEN"
            >
              <button className="text-link" onClick={() => go("clients")}>
                Alle ansehen <Icon name="arrow" size={15} />
              </button>
            </SectionTitle>
            <div className="client-mini-grid">
              {data.clients.slice(0, 3).map((client) => (
                <button
                  key={client.id}
                  onClick={() => go("clients/" + client.id)}
                  className="client-mini"
                >
                  <Avatar name={client.name} />
                  <strong>{client.name}</strong>
                  <span>{client.themes[0] || "Persönliche Begleitung"}</span>
                  <Icon name="arrow" size={16} />
                </button>
              ))}
            </div>
            {!data.clients.length && (
              <Empty
                title="Hier beginnt Begleitung."
                action={
                  <button
                    className="button secondary"
                    onClick={() => go("clients")}
                  >
                    Klienten anlegen
                  </button>
                }
              />
            )}
          </section>
        </div>
        <div className="dashboard-secondary">
          <section className="glass-card pause-card">
            <span className="card-icon heart">
              <Icon name="leaf" size={23} />
            </span>
            <span className="eyebrow">EIN MOMENT FÜR DICH</span>
            <h2>
              Erst ankommen.
              <br />
              Dann begleiten.
            </h2>
            <p>
              Spüre deine Füße am Boden. Atme in deinem eigenen Rhythmus. Was
              möchtest du heute in deinen Raum einladen?
            </p>
            <div className="pause-divider" />
            <span className="small-label">DEIN BEWUSSTER ANFANG</span>
            <div className="mini-ritual">
              <span>01</span> Einen Moment innehalten
            </div>
            <div className="mini-ritual">
              <span>02</span> Die eigene Intention finden
            </div>
            <div className="mini-ritual">
              <span>03</span> Offen in die Begegnung gehen
            </div>
          </section>
          <section className="learning-teaser">
            <span className="card-icon crown">
              <Icon name="book" size={21} />
            </span>
            <span className="eyebrow">DEIN NÄCHSTER IMPULS</span>
            <h2>{lesson?.title || "Wissen, das mit dir wächst."}</h2>
            <p>
              {lesson?.summary ||
                "Entdecke deinen Lernpfad: kurze Impulse, bewusste Reflexion und kleine Schritte."}
            </p>
            <button className="text-link" onClick={() => go("learning")}>
              Deinen Lernraum öffnen <Icon name="arrow" size={16} />
            </button>
          </section>
          <div className="quiet-quote">
            <Icon name="spark" size={18} />
            <p>
              „Entwicklung darf
              <br />
              sich nach dir anfühlen.“
            </p>
            <span>DEIN SENSE &amp; STARS-MOMENT</span>
          </div>
        </div>
      </div>
      {prepare && (
        <PrepareModal
          appointment={prepare}
          onClose={() => setPrepare(null)}
          {...props}
        />
      )}
    </>
  );
}
function Metric({
  icon,
  tone,
  value,
  label,
  detail,
}: {
  icon: IconName;
  tone: string;
  value: string;
  label: string;
  detail: string;
}) {
  return (
    <section className="metric glass-card">
      <span className={"card-icon " + tone}>
        <Icon name={icon} />
      </span>
      <div>
        <span className="metric-value">{value}</span>
        <h2>{label}</h2>
        <span className="metric-detail">{detail}</span>
      </div>
    </section>
  );
}
export function AppointmentRow({
  appointment: a,
  onPrepare,
  onCancel,
  onComplete,
  compact = false,
  client = false,
  practice = false,
}: {
  appointment: Appointment;
  onPrepare?: () => void;
  onCancel?: () => void;
  onComplete?: () => void;
  compact?: boolean;
  client?: boolean;
  practice?: boolean;
}) {
  return (
    <div className={"appointment-row " + (compact ? "compact" : "")}>
      <div className="date-tile">
        <strong>{dateFormat(a.start_at, { day: "2-digit" })}</strong>
        <span>{dateFormat(a.start_at, { month: "short" })}</span>
      </div>
      <div className="appointment-main">
        <h3>{client ? a.title : a.client_name}</h3>
        <p>
          {!client && (
            <>
              {a.title}
              <span className="bullet">·</span>
            </>
          )}
          {dateFormat(a.start_at, { hour: "2-digit", minute: "2-digit" })} Uhr{" "}
          <span className="bullet">·</span>
          {a.duration_minutes} Min.
          {!practice && (
            <>
              <span className="bullet">·</span>
              <span className="appointment-value">
                {money(a.price_cents)} Sitzungswert
              </span>
            </>
          )}
        </p>
        <div className="appointment-badges">
          <Badge
            tone={
              a.status === "in_progress"
                ? "green"
                : a.status === "cancelled"
                  ? "neutral"
                  : "orange"
            }
          >
            {statusName[a.status]}
          </Badge>
          {a.prepared && a.status === "scheduled" && (
            <span className="prepared-label">
              <Icon name="shield" size={12} /> Schutzraum bestätigt
            </span>
          )}
        </div>
      </div>
      <div className="appointment-actions">
        {!client && a.status === "scheduled" && onPrepare && (
          <button className="button small secondary" onClick={onPrepare}>
            {a.prepared ? "Sitzung beginnen" : "Schutzraum öffnen"}
            <Icon name={a.prepared ? "play" : "shield"} size={15} />
          </button>
        )}
        {!client && a.status === "in_progress" && onComplete && (
          <button className="button small secondary" onClick={onComplete}>
            <Icon name="check" size={15} /> Abschließen
          </button>
        )}
        {onCancel && a.status === "scheduled" && (
          <button className="button small text" onClick={onCancel}>
            Absagen
          </button>
        )}
      </div>
    </div>
  );
}
function PrepareModal({
  appointment,
  onClose,
  refresh,
  notify,
}: PageProps & { appointment: Appointment; onClose: () => void }) {
  const isCurrent = useRequestScope();
  const actionLock = useRef(false);
  const [ack, setAck] = useState(false),
    [prepared, setPrepared] = useState(appointment.prepared),
    [busy, setBusy] = useState(false),
    [error, setError] = useState("");
  async function confirm() {
    if (actionLock.current) return;
    actionLock.current = true;
    setBusy(true);
    setError("");
    try {
      if (!prepared) {
        await api(`/appointments/${appointment.id}/prepare`, {
          acknowledged: true,
        });
        if (isCurrent()) setPrepared(true);
        refresh();
        notify(
          "Der Schutzraum ist bestätigt. Du kannst die Sitzung jetzt bewusst beginnen.",
        );
      } else {
        await api(`/appointments/${appointment.id}/start`, {});
        refresh();
        notify("Die Sitzung wurde begonnen.");
        if (isCurrent()) onClose();
      }
    } catch (e) {
      if (isCurrent()) setError((e as Error).message);
    } finally {
      actionLock.current = false;
      if (isCurrent()) setBusy(false);
    }
  }
  return (
    <Modal
      title="Bewusst in die Begegnung."
      description={`Deine Sitzung mit ${appointment.client_name}`}
      onClose={() => {
        if (!actionLock.current) onClose();
      }}
    >
      <div className="protection-banner">
        <Icon name="shield" size={30} />
        <div>
          <strong>Dein Schutzraum</strong>
          <p>
            Ein kurzer Moment für einen klaren, verantwortungsvollen Rahmen.
          </p>
        </div>
      </div>
      <ol className="protection-list">
        <li>
          <strong>Bei dir ankommen</strong>
          <p>
            Spüre deine Füße oder den Kontakt zur Sitzfläche. Atme in deinem
            eigenen Rhythmus und nimm deine Aufmerksamkeit zu dir.
          </p>
        </li>
        <li>
          <strong>Deinen Rahmen spüren</strong>
          <p>
            „Ich begleite, ohne alles übernehmen zu müssen.“ Du darfst
            pausieren, Grenzen benennen oder eine Sitzung beenden.
          </p>
        </li>
        <li>
          <strong>Eine persönliche Grenze vorstellen</strong>
          <p>
            Wenn es zu dir passt, stelle dir einen ruhigen Raum um dich vor.
            Diese freiwillige spirituelle Visualisierung ist eine Metapher.
          </p>
        </li>
      </ol>
      <p className="protection-scope">
        Ein persönliches Vorbereitungsritual. Es ersetzt keine fachliche
        Behandlung oder die Klärung von Einverständnis und Vertraulichkeit mit
        deinem Gegenüber.
      </p>
      {prepared ? (
        <div className="alert success">
          <Icon name="check" /> Der Schutzraum wurde für diese Sitzung
          bestätigt.
        </div>
      ) : (
        <label className="checkbox-label">
          <input
            type="checkbox"
            checked={ack}
            onChange={(e) => setAck(e.target.checked)}
          />
          <span>
            Ich bin bei mir und habe meinen Rahmen für diese Sitzung geklärt.
          </span>
        </label>
      )}
      <ErrorBox error={error} />
      <div className="form-actions">
        <button className="button text" disabled={busy} onClick={onClose}>
          Zurück
        </button>
        <button
          className="button primary"
          disabled={busy || (!prepared && !ack)}
          onClick={confirm}
        >
          {busy
            ? "Wird gespeichert …"
            : prepared
              ? "Sitzung beginnen"
              : "Schutzraum bestätigen"}
          <Icon name={prepared ? "play" : "shield"} size={17} />
        </button>
      </div>
    </Modal>
  );
}
export function CalendarPage(props: PageProps) {
  const { data, loading, error } = useData<Appointment[]>(
    "/appointments" +
      (props.user.role === "client" ? "" : modeQuery(props.practice)),
    props.revision,
  );
  const clients = useData<Client[]>(
    props.user.role === "client"
      ? null
      : "/clients" + modeQuery(props.practice),
    props.revision,
  );
  const [create, setCreate] = useState(false),
    [prepare, setPrepare] = useState<Appointment | null>(null),
    [cancel, setCancel] = useState<Appointment | null>(null),
    [filter, setFilter] = useState("upcoming"),
    [actionError, setActionError] = useState(""),
    [busy, setBusy] = useState(false);
  const client = props.user.role === "client";
  const sorted = (data || [])
    .filter((a) =>
      filter === "all" || filter === "completed"
        ? filter === "all" || a.status === "completed"
        : a.status === "scheduled" || a.status === "in_progress",
    )
    .sort((a, b) => a.start_at.localeCompare(b.start_at));
  async function change(a: Appointment, status: string) {
    setBusy(true);
    setActionError("");
    try {
      await api(`/appointments/${a.id}`, { status }, "PATCH");
      props.refresh();
      props.notify(
        status === "cancelled"
          ? "Der Termin wurde abgesagt."
          : "Die Sitzung ist abgeschlossen.",
      );
      setCancel(null);
    } catch (e) {
      setActionError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <>
      <div className="page-heading">
        <div>
          <span className="eyebrow">RAUM FÜR BEGEGNUNG</span>
          <h1>
            {client
              ? "Zeit für dich."
              : props.practice
                ? "Sitzungen in Ruhe ausprobieren."
                : "Deine Zeit, bewusst geplant."}{" "}
            {!client && <ContextHelp topic="calendar" />}
          </h1>
          <p>Alle Termine in der Praxiszeitzone Europa/Berlin.</p>
        </div>
        <button
          className="button primary orange-button"
          onClick={() => setCreate(true)}
        >
          <Icon name="plus" size={18} />
          {client ? "Termin buchen" : "Termin planen"}
        </button>
      </div>
      <div className="calendar-layout">
        <section className="glass-card calendar-agenda" data-tour="protection">
          <div className="agenda-toolbar">
            <div className="segmented" aria-label="Termine filtern">
              {[
                ["upcoming", "Kommend"],
                ["completed", "Abgeschlossen"],
                ["all", "Alle Termine"],
              ].map(([id, label]) => (
                <button
                  key={id}
                  onClick={() => setFilter(id)}
                  className={filter === id ? "selected" : ""}
                  aria-pressed={filter === id}
                >
                  {label}
                </button>
              ))}
            </div>
            <span className="muted">
              {sorted.length} {sorted.length === 1 ? "Termin" : "Termine"}
            </span>
          </div>
          <ErrorBox error={error || actionError} />
          {loading && !data ? (
            <Loading />
          ) : sorted.length ? (
            sorted.map((a) => (
              <AppointmentRow
                key={a.id}
                appointment={a}
                practice={props.practice}
                client={client}
                onPrepare={() => setPrepare(a)}
                onCancel={client ? undefined : () => setCancel(a)}
                onComplete={() => void change(a, "completed")}
              />
            ))
          ) : (
            <Empty
              icon="calendar"
              title="Hier ist noch Raum frei."
              action={
                <button
                  className="button secondary"
                  onClick={() => setCreate(true)}
                >
                  {client ? "Ersten Termin buchen" : "Neuen Termin planen"}
                </button>
              }
            >
              Keine Termine in dieser Ansicht.
            </Empty>
          )}
        </section>
        <aside>
          <section className="glass-card calendar-side">
            <span className="card-icon sacral">
              <Icon name="calendar" />
            </span>
            <span className="eyebrow">GUT ZU WISSEN</span>
            <h2>Bewusst Zeit schaffen.</h2>
            <p>
              Termine sind zwischen 8 und 19 Uhr möglich. Plane 15 bis 180
              Minuten für deine Begegnung ein.
            </p>
            <div className="info-row">
              <Icon name="clock" size={17} />
              <span>
                Praxiszeitzone
                <br />
                <strong>Europa/Berlin</strong>
              </span>
            </div>
            <div className="info-row">
              <Icon name="shield" size={17} />
              <span>
                {client
                  ? "Deine Buchung bleibt persönlich."
                  : "Schutzraum vor jeder Sitzung."}
                <br />
                <strong>Mit bewusstem Rahmen</strong>
              </span>
            </div>
            <p className="fineprint">
              Die lokale Buchung versendet keine Nachricht und führt keine
              Zahlung aus.
            </p>
          </section>
        </aside>
      </div>
      {create && (
        <AppointmentForm
          {...props}
          clients={client ? [] : clients.data || []}
          onClose={() => setCreate(false)}
        />
      )}{" "}
      {prepare && (
        <PrepareModal
          {...props}
          appointment={prepare}
          onClose={() => setPrepare(null)}
        />
      )}{" "}
      {cancel && (
        <Modal
          title="Termin absagen?"
          description={`${cancel.client_name} · ${dateFormat(cancel.start_at, { day: "numeric", month: "long", hour: "2-digit", minute: "2-digit" })} Uhr`}
          onClose={() => setCancel(null)}
        >
          <p>
            Der Termin wird als abgesagt markiert. Es wird keine Nachricht
            versendet.
          </p>
          <ErrorBox error={actionError} />
          <div className="form-actions">
            <button className="button text" onClick={() => setCancel(null)}>
              Zurück
            </button>
            <button
              disabled={busy}
              className="button primary"
              onClick={() => void change(cancel, "cancelled")}
            >
              Termin absagen
            </button>
          </div>
        </Modal>
      )}
    </>
  );
}
function AppointmentForm({
  user,
  clients,
  onClose,
  refresh,
  notify,
  practice,
}: PageProps & { clients: Client[]; onClose: () => void }) {
  const isCurrent = useRequestScope();
  const saveLock = useRef(false);
  const originalPractice = practice === true;
  const [duration, setDuration] = useState(60);
  const [manualPrice, setManualPrice] = useState(false);
  const [price, setPrice] = useState("");
  const proposedPrice = suggestedPrice(user.hourly_rate_cents, duration);
  const [busy, setBusy] = useState(false),
    [error, setError] = useState("");
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (saveLock.current) return;
    const f = new FormData(event.currentTarget);
    if (
      user.role !== "client" &&
      !clients.some(
        (person) =>
          person.id === Number(f.get("client_id")) &&
          clientMatchesWorkspace(person, originalPractice),
      )
    ) {
      setError("Wähle eine Person aus diesem Arbeitsbereich.");
      return;
    }
    saveLock.current = true;
    setBusy(true);
    setError("");
    try {
      const startAt = toBerlinISO(String(f.get("start_at")));
      const manualCents = manualPrice ? euroToCents(price) : null;
      if (
        user.role !== "client" &&
        !practice &&
        manualPrice &&
        manualCents === null
      )
        throw new Error(
          "Bitte gib den vereinbarten Betrag ein. Für eine kostenlose Sitzung trage 0 ein.",
        );
      await api("/appointments", {
        client_id:
          user.role === "client" ? user.client_id : Number(f.get("client_id")),
        start_at: startAt,
        title: f.get("title"),
        duration_minutes: Number(f.get("duration_minutes")),
        price_cents:
          user.role === "client" || practice
            ? 0
            : manualPrice
              ? manualCents
              : null,
      });
      refresh();
      notify(
        user.role === "client"
          ? "Dein Termin ist gebucht."
          : "Der Termin ist angelegt.",
      );
      if (isCurrent()) onClose();
    } catch (e) {
      if (isCurrent()) setError((e as Error).message);
    } finally {
      saveLock.current = false;
      if (isCurrent()) setBusy(false);
    }
  }
  return (
    <Modal
      title={
        user.role === "client"
          ? "Deine nächste Begegnung."
          : "Zeit für eine neue Begegnung."
      }
      description={
        practice
          ? "Ein Testtermin für eine fiktive Person. Er bleibt von deiner Praxis getrennt."
          : "Wähle einen freien Zeitpunkt. Überschneidungen werden geprüft."
      }
      onClose={() => {
        if (!saveLock.current) onClose();
      }}
    >
      <form onSubmit={submit} className="form-grid">
        {user.role !== "client" && (
          <label className="full">
            {practice ? "Testperson" : "Klient"}
            <select disabled={busy} name="client_id" required defaultValue="">
              <option value="" disabled>
                Bitte auswählen
              </option>
              {clients.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name}
                </option>
              ))}
            </select>
          </label>
        )}
        <label className="full">
          Art der Sitzung
          <input
            readOnly={busy}
            name="title"
            required
            maxLength={120}
            defaultValue="Persönliche Beratung"
          />
        </label>
        <label>
          Datum & Uhrzeit
          <input
            type="datetime-local"
            readOnly={busy}
            name="start_at"
            defaultValue={nextAppointmentTime()}
            required
          />
          <small>Europe/Berlin · 08:00–19:00 Uhr</small>
        </label>
        <label>
          Dauer
          <select
            disabled={busy}
            name="duration_minutes"
            value={duration}
            onChange={(event) => setDuration(Number(event.target.value))}
          >
            {[15, 30, 45, 60, 90, 120, 180].map((n) => (
              <option value={n} key={n}>
                {n} Minuten
              </option>
            ))}
          </select>
        </label>
        {user.role !== "client" && !practice && (
          <section
            className="full appointment-price"
            aria-label="Sitzungspreis"
          >
            <div>
              <span className="small-label">SITZUNGSPREIS</span>
              <strong>
                {manualPrice
                  ? "Individuelle Vereinbarung"
                  : money(proposedPrice)}
              </strong>
            </div>
            <p>
              {user.hourly_rate_cents == null
                ? "Noch kein Stundensatz hinterlegt. Du kannst ihn in den Einstellungen festlegen."
                : `${money(user.hourly_rate_cents)} pro Stunde · ${duration} Minuten`}
            </p>
            <label className="academy-check">
              <input
                type="checkbox"
                checked={manualPrice}
                disabled={busy}
                onChange={(event) => {
                  setManualPrice(event.target.checked);
                  if (event.target.checked)
                    setPrice((proposedPrice / 100).toFixed(2));
                }}
              />
              Sitzungspreis manuell anpassen
            </label>
            {manualPrice && (
              <label>
                Vereinbarter Betrag in €
                <input
                  inputMode="decimal"
                  name="price"
                  value={price}
                  onChange={(event) => setPrice(event.target.value)}
                  readOnly={busy}
                  required
                />
                <small>
                  0 € ist eine kostenlose Sitzung. Der vereinbarte Betrag bleibt
                  für diesen Termin erhalten.
                </small>
              </label>
            )}
            <small>
              Der Sitzungswert dient deiner Übersicht. Es wird keine Rechnung
              oder Zahlung ausgelöst.
            </small>
          </section>
        )}
        <div className="full">
          <ErrorBox error={error} />
        </div>
        <div className="form-actions full">
          <button
            type="button"
            className="button text"
            disabled={busy}
            onClick={onClose}
          >
            Abbrechen
          </button>
          <button disabled={busy} className="button primary orange-button">
            {busy
              ? "Wird geprüft …"
              : user.role === "client"
                ? "Verbindlich lokal buchen"
                : "Termin anlegen"}
            <Icon name="check" size={17} />
          </button>
        </div>
      </form>
    </Modal>
  );
}
export function ClientsPage(props: PageProps) {
  const { data, loading, error } = useData<Client[]>(
    "/clients" + modeQuery(props.practice),
    props.revision,
  );
  const archived = useData<Client[]>(
    props.practice ? "/clients?practice=1&archived=1" : null,
    props.revision,
  );
  const [query, setQuery] = useState(""),
    [create, setCreate] = useState(false),
    [actionError, setActionError] = useState(""),
    [busy, setBusy] = useState(false),
    [reset, setReset] = useState(false);
  const filtered = (data || []).filter((c) =>
    (c.name + " " + c.email + " " + c.themes.join(" "))
      .toLowerCase()
      .includes(query.toLowerCase()),
  );
  async function action(path: string, message: string) {
    if (busy) return;
    setBusy(true);
    setActionError("");
    try {
      await api(path, {});
      props.refresh();
      props.notify(message);
      setReset(false);
    } catch (e) {
      setActionError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <>
      <div className="page-heading">
        <div>
          <span className="eyebrow">
            {props.practice
              ? "DEIN GESCHÜTZTER ÜBUNGSRAUM"
              : "MENSCHEN IM MITTELPUNKT"}
          </span>
          <h1>
            {props.practice
              ? "Ausprobieren. Lernen. Neu beginnen."
              : "Jeder Weg ist persönlich."}{" "}
            <ContextHelp topic={props.practice ? "practice" : "clients"} />
          </h1>
          <p>
            {props.practice
              ? "Fiktive Personen für deinen eigenen Probedurchlauf. Ohne Einfluss auf deine Praxisdaten."
              : "Ein klarer Blick auf die Menschen, die du begleitest."}
          </p>
        </div>
        <button className="button primary" onClick={() => setCreate(true)}>
          <Icon name="plus" size={18} />
          {props.practice ? "Testperson anlegen" : "Klient anlegen"}
        </button>
      </div>
      {props.practice && (
        <section className="glass-card practice-tools">
          <div>
            <h2>Ein guter Einstieg.</h2>
            <p>
              Drei fiktive Beispiele mit vollständigen Geburtsangaben und
              berechnetem Radix. Bereits vorhandene aktive Beispiele werden beim
              erneuten Laden wiederverwendet.
            </p>
          </div>
          <div className="practice-tool-actions">
            <button
              className="button secondary"
              disabled={busy}
              onClick={() =>
                void action(
                  "/practice/clients/examples",
                  "Die fiktiven Beispiele sind bereit.",
                )
              }
            >
              <Icon name="users" size={18} />
              {busy ? "Wird vorbereitet …" : "Drei Beispiele laden"}
            </button>
            <button
              className="button text"
              disabled={busy || !data?.length}
              onClick={() => setReset(true)}
            >
              <Icon name="refresh" size={17} />
              Übungsraum zurücksetzen
            </button>
          </div>
        </section>
      )}
      <ErrorBox error={actionError} />
      <section className="glass-card clients-panel">
        <div className="list-toolbar">
          <div>
            <h2>
              {props.practice ? "Deine Testpersonen" : "Deine Klienten"}{" "}
              <span className="count">{data?.length || 0}</span>
            </h2>
            <p>
              {props.practice
                ? "Ausschließlich deine eigenen fiktiven Daten."
                : "Individuelle Begleitung. An einem Ort."}
            </p>
          </div>
          <label className="search-field">
            <Icon name="search" size={19} />
            <span className="visually-hidden">
              {props.practice ? "Testpersonen suchen" : "Klienten suchen"}
            </span>
            <input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Name oder Thema suchen …"
            />
          </label>
        </div>
        <ErrorBox error={error} />
        {loading && !data ? (
          <Loading />
        ) : (
          <div className="client-grid">
            {filtered.map((c) => (
              <button
                className="client-card"
                key={c.id}
                onClick={() => go("clients/" + c.id)}
              >
                <div className="client-card-top">
                  <Avatar name={c.name} size="large" />
                  <Icon name="arrow" size={18} />
                </div>
                <h3>{c.name}</h3>
                <p>{c.email}</p>
                <div className="theme-list">
                  {c.is_test && <Badge tone="demo">Fiktive Testperson</Badge>}
                  {c.themes.slice(0, 3).map((t) => (
                    <Badge key={t}>{t}</Badge>
                  ))}
                </div>
                <div className="client-card-footer">
                  <span>
                    <Icon name={c.chart ? "orbit" : "leaf"} size={14} />
                    {c.chart
                      ? "Sternenkarte vorhanden"
                      : "Persönliche Begleitung"}
                  </span>
                </div>
              </button>
            ))}
          </div>
        )}
        {!loading && !filtered.length && (
          <Empty
            icon="users"
            title={
              query
                ? "Kein passender Eintrag gefunden."
                : props.practice
                  ? "Dein Übungsraum ist bereit."
                  : "Hier beginnt Verbindung."
            }
          >
            {query
              ? "Versuche einen anderen Namen oder ein anderes Thema."
              : props.practice
                ? "Lade die drei Beispiele oder lege deine erste fiktive Testperson an."
                : "Lege den ersten Klienten für deine Praxis an."}
          </Empty>
        )}
      </section>
      {props.practice && (
        <details className="glass-card practice-archive">
          <summary>
            Testarchiv · {archived.data?.length || 0} gelöschte Testpersonen
          </summary>
          <p>
            Gelöschte Testpersonen bleiben hier wiederherstellbar. Echte
            Klienten sind von diesen Aktionen ausgeschlossen.
          </p>
          <ErrorBox error={archived.error} />
          {archived.data?.length ? (
            <ul>
              {archived.data.map((c) => (
                <li key={c.id}>
                  <span>
                    <strong>{c.name}</strong>
                    <small>Fiktive Testperson · im Archiv</small>
                  </span>
                  <button
                    className="button secondary small"
                    disabled={busy}
                    onClick={() =>
                      void action(
                        `/practice/clients/${c.id}/restore`,
                        "Die Testperson ist wiederhergestellt.",
                      )
                    }
                  >
                    Wiederherstellen
                  </button>
                </li>
              ))}
            </ul>
          ) : (
            <p>Noch keine Testperson im Archiv.</p>
          )}
        </details>
      )}
      {create && <ClientForm {...props} onClose={() => setCreate(false)} />}
      {reset && (
        <Modal
          title="Den Übungsraum neu beginnen?"
          description="Nur deine eigenen aktiven Testpersonen werden ins Testarchiv verschoben."
          onClose={() => {
            if (!busy) setReset(false);
          }}
        >
          <p>
            Die zugehörigen Testtermine verschwinden aus der aktiven
            Übungsansicht. Deine Praxisdaten, Lektionen und persönlichen
            Lernnotizen bleiben erhalten. Du kannst die Testpersonen später im
            Testarchiv wiederherstellen.
          </p>
          <ErrorBox error={actionError} />
          <div className="form-actions">
            <button
              className="button text"
              disabled={busy}
              onClick={() => setReset(false)}
            >
              Zurück
            </button>
            <button
              className="button primary"
              disabled={busy}
              onClick={() =>
                void action(
                  "/practice/reset",
                  "Dein Übungsraum ist wieder frei. Testpersonen liegen im Testarchiv.",
                )
              }
            >
              {busy ? "Wird zurückgesetzt …" : "Eigene Testdaten zurücksetzen"}
            </button>
          </div>
        </Modal>
      )}
    </>
  );
}

function ClientForm({
  client,
  onClose,
  refresh,
  notify,
  practice,
}: PageProps & { client?: Client; onClose: () => void }) {
  const originalPractice = practice === true;
  const isCurrent = useRequestScope();
  const saveLock = useRef(false);
  const [busy, setBusy] = useState(false),
    [error, setError] = useState("");
  const [testEmail] = useState(
    () => "testperson-" + crypto.randomUUID().slice(0, 8) + "@example.org",
  );
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (saveLock.current) return;
    if (client && !clientMatchesWorkspace(client, originalPractice)) {
      setError("Dieses Profil gehört nicht zum gewählten Arbeitsbereich.");
      return;
    }
    const f = new FormData(event.currentTarget);
    saveLock.current = true;
    setBusy(true);
    setError("");
    try {
      const value = {
        name: String(f.get("name")),
        email: String(f.get("email")),
        birth_date: f.get("birth_date") || null,
        birth_time: f.get("birth_time") || null,
        birth_place: f.get("birth_place") || null,
        themes: String(f.get("themes") || "")
          .split(",")
          .map((t) => t.trim())
          .filter(Boolean),
      };
      const saved = await api<Client>(
        client
          ? `/clients/${client.id}`
          : originalPractice
            ? "/practice/clients"
            : "/clients",
        value,
        client ? "PATCH" : "POST",
      );
      if (!clientMatchesWorkspace(saved, originalPractice))
        throw new Error(
          "Die gespeicherte Person gehört nicht zum erwarteten Arbeitsbereich. Bitte lade die passende Liste neu.",
        );
      refresh();
      notify(
        client
          ? "Die Klientendaten sind gespeichert."
          : practice
            ? "Die fiktive Testperson ist angelegt."
            : "Der Klient ist angelegt. Ein Portal-Konto wird separat erstellt.",
      );
      if (isCurrent()) {
        onClose();
        if (!client) go("clients/" + saved.id, originalPractice);
      }
    } catch (e) {
      if (isCurrent()) setError((e as Error).message);
    } finally {
      saveLock.current = false;
      if (isCurrent()) setBusy(false);
    }
  }
  return (
    <Modal
      title={
        client
          ? "Den Menschen im Blick behalten."
          : practice
            ? "Eine neue fiktive Testperson."
            : "Ein neuer Mensch in deinem Raum."
      }
      description={
        practice
          ? "Nutze ausschließlich erfundene Angaben. Geburtsangaben sind optional und für eine eigene Sternenkarte erforderlich."
          : "Geburtsangaben sind optional und werden erst für die Sternenkarte benötigt."
      }
      onClose={() => {
        if (!saveLock.current) onClose();
      }}
    >
      <form className="form-grid" onSubmit={submit}>
        <label className="full">
          Vor- und Nachname
          <input
            readOnly={busy}
            name="name"
            required
            maxLength={120}
            autoComplete="off"
            defaultValue={client?.name}
          />
        </label>
        <label className="full">
          E-Mail-Adresse
          <input
            readOnly={busy}
            name="email"
            type="email"
            required
            maxLength={254}
            autoComplete="off"
            defaultValue={client?.email || (practice ? testEmail : "")}
          />
        </label>
        <label>
          Geburtsdatum <span className="optional">optional</span>
          <input
            readOnly={busy}
            name="birth_date"
            type="date"
            max={new Date().toISOString().slice(0, 10)}
            defaultValue={client?.birth_date || ""}
          />
        </label>
        <label>
          Geburtszeit <span className="optional">Ortszeit</span>
          <input
            readOnly={busy}
            name="birth_time"
            type="time"
            defaultValue={client?.birth_time || ""}
          />
        </label>
        <label className="full">
          Geburtsort <span className="optional">optional</span>
          <input
            readOnly={busy}
            name="birth_place"
            maxLength={200}
            defaultValue={client?.birth_place || ""}
            placeholder="z. B. Hamburg, Deutschland"
          />
        </label>
        <label className="full">
          Begleitungsthemen{" "}
          <span className="optional">durch Kommas getrennt</span>
          <input
            readOnly={busy}
            name="themes"
            maxLength={500}
            defaultValue={client?.themes.join(", ") || ""}
            placeholder="Selbstvertrauen, Neuorientierung"
          />
        </label>
        <div className="full">
          <ErrorBox error={error} />
        </div>
        <div className="form-actions full">
          <button
            type="button"
            className="button text"
            disabled={busy}
            onClick={onClose}
          >
            Abbrechen
          </button>
          <button className="button primary" disabled={busy}>
            {busy
              ? "Wird gespeichert …"
              : client
                ? "Änderungen speichern"
                : practice
                  ? "Testperson anlegen"
                  : "Klient anlegen"}
            <Icon name="check" size={17} />
          </button>
        </div>
      </form>
    </Modal>
  );
}
export function ClientPage(props: PageProps & { id: number }) {
  const {
    data: client,
    loading,
    error,
  } = useData<Client>(`/clients/${props.id}`, props.revision);
  const isCurrent = useRequestScope();
  const resources = useData<Resource[]>(
    client && clientMatchesWorkspace(client, props.practice)
      ? `/clients/${props.id}/resources`
      : null,
    props.revision,
  );
  const [tab, setTab] = useState("overview"),
    [edit, setEdit] = useState(false),
    [resource, setResource] = useState(false),
    [account, setAccount] = useState(false),
    [actionError, setActionError] = useState(""),
    [remove, setRemove] = useState(false),
    [removing, setRemoving] = useState(false);
  if (loading && !client) return <Loading />;
  if (!client) return <ErrorBox error={error} />;
  if (!clientMatchesWorkspace(client, props.practice))
    return (
      <section className="glass-card detail-card">
        <Empty
          icon="shield"
          title="Dieses Profil gehört nicht zu diesem Arbeitsbereich."
          action={
            <button
              className="button secondary"
              onClick={() => go("clients", props.practice === true)}
            >
              Zur {props.practice ? "Testpersonenliste" : "Klientenliste"}
              <Icon name="arrow" size={16} />
            </button>
          }
        >
          Praxis und Übungsraum bleiben getrennt. Öffne eine Person aus der
          passenden Liste. Für dieses Profil stehen hier keine
          Bearbeitungsaktionen bereit.
        </Empty>
      </section>
    );
  async function shareChart() {
    setActionError("");
    try {
      await api(
        `/clients/${props.id}`,
        { chart_shared: !client?.chart_shared },
        "PATCH",
      );
      props.refresh();
      props.notify(
        client?.chart_shared
          ? "Die Sternenkarte ist jetzt privat."
          : "Die Sternenkarte ist im persönlichen Portal freigegeben.",
      );
    } catch (e) {
      setActionError((e as Error).message);
    }
  }
  return (
    <>
      <button className="back-link" onClick={() => go("clients")}>
        <Icon name="arrow" size={15} /> Alle Klienten
      </button>
      {client.is_test && (
        <div className="test-profile-label">
          <Badge tone="demo">Fiktive Testperson</Badge>
          <span>Nur für deinen Übungsraum</span>
        </div>
      )}
      <section className="client-profile glass-card">
        <Avatar name={client.name} size="large" />
        <div className="profile-info">
          <span className="eyebrow">PERSÖNLICHE BEGLEITUNG</span>
          <h1>{client.name}</h1>
          <p>
            <Icon name="mail" size={15} />
            {client.email}
          </p>
          <div className="theme-list">
            {client.themes.map((t) => (
              <Badge key={t}>{t}</Badge>
            ))}
          </div>
        </div>
        <div className="profile-actions">
          <button className="button secondary" onClick={() => setEdit(true)}>
            Profil bearbeiten
          </button>
          {client.is_test && (
            <button className="button text" onClick={() => setRemove(true)}>
              Testperson löschen
            </button>
          )}
          {props.user.role === "admin" && !client.is_test && (
            <button className="button text" onClick={() => setAccount(true)}>
              <Icon name="lock" size={15} /> Portal-Zugang anlegen
            </button>
          )}
        </div>
      </section>
      <div className="page-tabs" role="tablist" aria-label="Klientenansicht">
        {[
          ["overview", "Überblick", "users"],
          ["chart", "Sternenkarte", "orbit"],
          ["resources", "Begleitung", "heart"],
        ].map(([id, label, icon]) => (
          <button
            key={id}
            id={"tab-" + id}
            role="tab"
            aria-selected={tab === id}
            aria-controls={"panel-" + id}
            tabIndex={tab === id ? 0 : -1}
            onClick={() => setTab(id)}
            onKeyDown={(e) => {
              if (e.key === "ArrowRight" || e.key === "ArrowLeft") {
                e.preventDefault();
                const ids = ["overview", "chart", "resources"];
                const next =
                  ids[
                    (ids.indexOf(tab) + (e.key === "ArrowRight" ? 1 : 2)) % 3
                  ];
                setTab(next);
                document.getElementById("tab-" + next)?.focus();
              }
            }}
            className={tab === id ? "active" : ""}
          >
            <Icon name={icon as IconName} size={17} />
            {label}
          </button>
        ))}
      </div>
      <ErrorBox error={error || actionError} />
      <div role="tabpanel" id={"panel-" + tab} aria-labelledby={"tab-" + tab}>
        {tab === "overview" ? (
          <div className="detail-grid">
            <section className="glass-card detail-card">
              <SectionTitle
                title="Die persönliche Basis"
                eyebrow="BEWUSST KENNENLERNEN"
              />
              <dl className="details-list">
                <div>
                  <dt>Geburtstag</dt>
                  <dd>
                    {client.birth_date
                      ? dateFormat(client.birth_date)
                      : "Noch nicht hinterlegt"}
                  </dd>
                </div>
                <div>
                  <dt>Geburtszeit</dt>
                  <dd>
                    {client.birth_time
                      ? client.birth_time.slice(0, 5) + " Uhr (Ortszeit)"
                      : "Noch nicht hinterlegt"}
                  </dd>
                </div>
                <div>
                  <dt>Geburtsort</dt>
                  <dd>{client.birth_place || "Noch nicht hinterlegt"}</dd>
                </div>
                <div>
                  <dt>Begleitung seit</dt>
                  <dd>{dateFormat(client.created_at)}</dd>
                </div>
              </dl>
              <button
                className="button secondary"
                onClick={() => setTab("chart")}
              >
                <Icon name="orbit" size={18} />
                {client.chart
                  ? "Sternenkarte ansehen"
                  : "Sternenkarte berechnen"}
              </button>
            </section>
            <section className="glass-card detail-card">
              <SectionTitle
                title="Was du bewusst teilst"
                eyebrow="DEIN VERTRAUENSRAUM"
              />
              <div className="sharing-number">
                {(resources.data || []).filter((r) => r.shared).length}
                <span>freigegebene Impulse</span>
              </div>
              <p>
                Notizen und Übungen bleiben privat, bis du sie ausdrücklich für
                das persönliche Portal freigibst.
              </p>
              <button
                className="button secondary"
                onClick={() => setTab("resources")}
              >
                Begleitung öffnen <Icon name="arrow" size={16} />
              </button>
            </section>
          </div>
        ) : tab === "chart" ? (
          <>
            <ChartBuilder {...props} client={client} />
            {client.chart && !client.is_test && (
              <div className="chart-share-bar glass-card">
                <div>
                  <Icon name={client.chart_shared ? "eye" : "lock"} size={22} />
                  <span>
                    <strong>
                      {client.chart_shared
                        ? "Im Portal freigegeben"
                        : "Sternenkarte ist privat"}
                    </strong>
                    <small>
                      {client.chart_shared
                        ? "Der Klient kann seine Karte im eigenen Raum sehen."
                        : "Du entscheidest bewusst, wann die Karte sichtbar wird."}
                    </small>
                  </span>
                </div>
                <button
                  className="button secondary"
                  onClick={() => void shareChart()}
                >
                  {client.chart_shared
                    ? "Freigabe zurücknehmen"
                    : "Im Portal freigeben"}
                </button>
              </div>
            )}
          </>
        ) : (
          <section className="glass-card resources-panel">
            <SectionTitle
              title="Impulse, die weiterbegleiten"
              eyebrow="ZWISCHEN DEN BEGEGNUNGEN"
            >
              <button
                className="button primary"
                onClick={() => setResource(true)}
              >
                <Icon name="plus" size={17} /> Impuls hinzufügen
              </button>
            </SectionTitle>
            <ErrorBox error={resources.error} />
            {resources.loading && !resources.data ? (
              <Loading />
            ) : resources.data?.length ? (
              <div className="resource-list">
                {resources.data.map((r) => (
                  <ResourceCard key={r.id} resource={r} {...props} />
                ))}
              </div>
            ) : (
              <Empty icon="heart" title="Was soll diese Begegnung begleiten?">
                Halte eine Notiz fest, gib eine Aufgabe mit oder teile einen
                Audio-Link.
              </Empty>
            )}
          </section>
        )}
      </div>
      {remove && (
        <Modal
          title="Testperson löschen?"
          description={client.name + " wird ins Testarchiv verschoben."}
          onClose={() => {
            if (!removing) setRemove(false);
          }}
        >
          <p>
            Die fiktive Person und ihre Testtermine verschwinden aus der aktiven
            Auswahl. Im Testarchiv kannst du die Person wiederherstellen. Echte
            Klienten werden dabei nicht verändert.
          </p>
          <ErrorBox error={actionError} />
          <div className="form-actions">
            <button
              className="button text"
              disabled={removing}
              onClick={() => setRemove(false)}
            >
              Zurück
            </button>
            <button
              className="button primary"
              disabled={removing}
              onClick={async () => {
                if (removing) return;
                setRemoving(true);
                setActionError("");
                try {
                  await api(
                    `/practice/clients/${client.id}`,
                    undefined,
                    "DELETE",
                  );
                  props.refresh();
                  props.notify("Die Testperson liegt jetzt im Testarchiv.");
                  if (isCurrent()) go("clients", props.practice === true);
                } catch (e) {
                  setActionError((e as Error).message);
                } finally {
                  setRemoving(false);
                }
              }}
            >
              {removing ? "Wird verschoben …" : "Ins Testarchiv verschieben"}
            </button>
          </div>
        </Modal>
      )}
      {edit && (
        <ClientForm {...props} client={client} onClose={() => setEdit(false)} />
      )}{" "}
      {resource && (
        <ResourceForm
          {...props}
          client={client}
          onClose={() => setResource(false)}
        />
      )}{" "}
      {account && (
        <PortalAccount
          {...props}
          client={client}
          onClose={() => setAccount(false)}
        />
      )}
    </>
  );
}
function PortalAccount({
  client,
  onClose,
  notify,
}: PageProps & { client: Client; onClose: () => void }) {
  const isCurrent = useRequestScope();
  const [password, setPassword] = useState(""),
    [busy, setBusy] = useState(false),
    [error, setError] = useState(""),
    [done, setDone] = useState(false);
  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      await api(`/clients/${client.id}/portal-account`, { password });
      if (isCurrent()) setDone(true);
      setPassword("");
      notify(
        "Der persönliche Portal-Zugang ist lokal angelegt. Es wurde nichts versendet.",
      );
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <Modal
      title="Ein persönlicher Zugang."
      description={`Portal-Konto für ${client.name}`}
      onClose={onClose}
    >
      {done ? (
        <>
          <div className="alert success">
            <Icon name="check" /> Der Zugang für {client.email} ist angelegt.
          </div>
          <p>
            Übergib das festgelegte Passwort über einen geeigneten persönlichen
            Weg. Sense &amp; Stars hat keine Nachricht versendet.
          </p>
          <div className="form-actions">
            <button className="button primary" onClick={onClose}>
              Verstanden
            </button>
          </div>
        </>
      ) : (
        <form onSubmit={submit}>
          <p>
            Das Konto sieht ausschließlich die eigenen, bewusst freigegebenen
            Inhalte.
          </p>
          <label>
            Persönliches Passwort
            <input
              type="password"
              minLength={12}
              maxLength={128}
              autoComplete="new-password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
            <small>Mindestens 12 Zeichen. Lokal und separat übergeben.</small>
          </label>
          <ErrorBox error={error} />
          <div className="form-actions">
            <button type="button" className="button text" onClick={onClose}>
              Abbrechen
            </button>
            <button className="button primary" disabled={busy}>
              {busy ? "Wird angelegt …" : "Zugang anlegen"}
              <Icon name="lock" size={16} />
            </button>
          </div>
        </form>
      )}
    </Modal>
  );
}
function ResourceForm({
  client,
  onClose,
  refresh,
  notify,
}: PageProps & { client: Client; onClose: () => void }) {
  const isCurrent = useRequestScope();
  const [kind, setKind] = useState<Resource["kind"]>("note"),
    [busy, setBusy] = useState(false),
    [error, setError] = useState("");
  async function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    setBusy(true);
    setError("");
    try {
      await api(`/clients/${client.id}/resources`, {
        kind,
        title: f.get("title"),
        body: f.get("body"),
        shared: f.get("shared") === "on",
        ...(kind === "audio" ? { audio_url: f.get("audio_url") } : {}),
      });
      refresh();
      notify(
        f.get("shared") === "on"
          ? "Der Impuls ist gespeichert und im Portal freigegeben."
          : "Der Impuls ist privat gespeichert.",
      );
      if (isCurrent()) onClose();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <Modal
      title="Ein Impuls für den weiteren Weg."
      description={`Begleitung für ${client.name}`}
      onClose={onClose}
    >
      <form onSubmit={submit} className="form-grid">
        <label className="full">
          Art des Impulses
          <select
            value={kind}
            onChange={(e) => setKind(e.target.value as Resource["kind"])}
          >
            {Object.entries(resourceName).map(([id, label]) => (
              <option key={id} value={id}>
                {label}
              </option>
            ))}
          </select>
        </label>
        <label className="full">
          Titel
          <input name="title" required maxLength={160} />
        </label>
        <label className="full">
          {kind === "task" ? "Aufgabe & Anleitung" : "Inhalt"}
          <textarea
            name="body"
            rows={5}
            required
            maxLength={20000}
            placeholder="Persönlich, klar und ohne Heilversprechen …"
          />
        </label>
        {kind === "audio" && (
          <label className="full">
            HTTPS-Audio-Link
            <input
              type="url"
              name="audio_url"
              pattern="https://.*"
              placeholder="https://…"
              required
            />
            <small>
              Nur ein vorhandener Link. Kein Upload und keine automatische
              Wiedergabe.
            </small>
          </label>
        )}
        <label className="checkbox-label full">
          <input type="checkbox" name="shared" />
          <span>Diesen Impuls bewusst im persönlichen Portal freigeben.</span>
        </label>
        <div className="full">
          <ErrorBox error={error} />
        </div>
        <div className="form-actions full">
          <button type="button" className="button text" onClick={onClose}>
            Abbrechen
          </button>
          <button disabled={busy} className="button primary">
            {busy ? "Wird gespeichert …" : "Impuls speichern"}
            <Icon name="check" size={17} />
          </button>
        </div>
      </form>
    </Modal>
  );
}
function ResourceCard({
  resource: r,
  readOnly = false,
  refresh,
  notify,
}: Pick<PageProps, "refresh" | "notify"> & {
  resource: Resource;
  readOnly?: boolean;
}) {
  const [error, setError] = useState(""),
    [busy, setBusy] = useState(false);
  async function toggle() {
    setBusy(true);
    setError("");
    try {
      await api(`/resources/${r.id}`, { shared: !r.shared }, "PATCH");
      refresh();
      notify(
        r.shared
          ? "Der Impuls ist jetzt privat."
          : "Der Impuls ist im Portal freigegeben.",
      );
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <article className={"resource-card resource-" + r.kind}>
      <div className="resource-header">
        <span
          className={
            "card-icon " +
            (r.kind === "note"
              ? "third-eye"
              : r.kind === "task"
                ? "heart"
                : "throat")
          }
        >
          <Icon
            name={
              r.kind === "note" ? "note" : r.kind === "task" ? "task" : "audio"
            }
            size={19}
          />
        </span>
        <span className="small-label">{resourceName[r.kind]}</span>
        {!readOnly && (
          <Badge tone={r.shared ? "green" : "neutral"}>
            <Icon name={r.shared ? "eye" : "lock"} size={11} />
            {r.shared ? "Freigegeben" : "Privat"}
          </Badge>
        )}
      </div>
      <h3>{r.title}</h3>
      <p className="resource-body">{r.body}</p>
      {r.kind === "audio" && r.audio_url?.startsWith("https://") && (
        <a
          className="button secondary small"
          href={r.audio_url}
          target="_blank"
          rel="noopener noreferrer"
        >
          <Icon name="play" size={15} /> Audio-Link öffnen
        </a>
      )}
      <div className="resource-footer">
        <span>{dateFormat(r.created_at)}</span>
        {!readOnly && (
          <button
            disabled={busy}
            className="text-link"
            onClick={() => void toggle()}
          >
            {r.shared ? "Privat stellen" : "Im Portal freigeben"}
            <Icon name={r.shared ? "lock" : "eye"} size={14} />
          </button>
        )}
      </div>
      <ErrorBox error={error} />
    </article>
  );
}
export function AstroPage(props: PageProps) {
  const { data, loading, error } = useData<Client[]>(
    "/clients" + modeQuery(props.practice),
    props.revision,
  );
  const [id, setId] = useState("");
  const selected = data?.find((c) => String(c.id) === id);
  return (
    <>
      <div className="page-heading">
        <div>
          <span className="eyebrow">PERSPEKTIVEN ENTDECKEN</span>
          <h1>
            Eine Karte. Viele Möglichkeiten. <ContextHelp topic="chart" />
          </h1>
          <p>
            Astronomisch berechnet. Als spiritueller Reflexionsraum betrachtet.
          </p>
        </div>
        <Icon name="orbit" size={38} />
      </div>
      <section className="glass-card chart-selector">
        <label>
          {props.practice
            ? "Welche fiktive Testperson möchtest du erkunden?"
            : "Für wen möchtest du die Sternenkarte öffnen?"}
          <select value={id} onChange={(e) => setId(e.target.value)}>
            <option value="">
              {props.practice
                ? "Testperson auswählen …"
                : "Klienten auswählen …"}
            </option>
            {data?.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name}
                {c.chart ? " · Karte vorhanden" : ""}
              </option>
            ))}
          </select>
        </label>
        <span>
          <Icon name="shield" size={18} />{" "}
          {props.mode === "hosted"
            ? "Geburtsangaben werden im geschützten Online-System gespeichert und verarbeitet."
            : "Geburtsangaben bleiben lokal."}
        </span>
      </section>
      <ErrorBox error={error} />
      {loading && !data ? (
        <Loading />
      ) : selected ? (
        <ChartBuilder key={selected.id} {...props} client={selected} />
      ) : (
        <section className="glass-card chart-intro">
          <div>
            <span className="card-icon throat">
              <Icon name="orbit" size={32} />
            </span>
            <h2>
              Ein neuer Blick
              <br />
              auf den eigenen Weg.
            </h2>
            <p>
              Wähle einen Klienten. Die Karte verbindet Planetenpositionen,
              Häuser und Aspekte mit einer nachvollziehbaren Berechnungsquelle.
            </p>
            <p className="fineprint">
              Für die Berechnung werden ein genaues Geburtsdatum, die
              Geburtszeit und ein eindeutig gewählter Ort benötigt.
            </p>
          </div>
          <OrbitArt />
        </section>
      )}
    </>
  );
}
function ChartBuilder({ client, ...props }: PageProps & { client: Client }) {
  const isCurrent = useRequestScope();
  const requestLock = useRef(false);
  const [query, setQuery] = useState(client.birth_place || ""),
    [places, setPlaces] = useState<Place[]>([]),
    [place, setPlace] = useState<Place | null>(null),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(""),
    [fold, setFold] = useState(""),
    [json, setJson] = useState(false);
  async function search(e: FormEvent) {
    e.preventDefault();
    if (requestLock.current || !clientMatchesWorkspace(client, props.practice))
      return;
    requestLock.current = true;
    setBusy("search");
    setError("");
    setPlace(null);
    setPlaces([]);
    try {
      const found = await api<Place[]>(
        "/astro/places?q=" + encodeURIComponent(query),
      );
      if (!isCurrent()) return;
      setPlaces(found);
      if (!found.length)
        setError("Kein passender Ort gefunden. Ergänze Region oder Land.");
    } catch (e) {
      if (isCurrent()) setError((e as Error).message);
    } finally {
      requestLock.current = false;
      if (isCurrent()) setBusy("");
    }
  }
  async function calculate() {
    if (
      !place ||
      requestLock.current ||
      !clientMatchesWorkspace(client, props.practice)
    )
      return;
    requestLock.current = true;
    setBusy("chart");
    setError("");
    try {
      await api(`/clients/${client.id}/chart`, {
        place_id: place.id,
        ...(fold !== "" ? { fold: Number(fold) } : {}),
      });
      props.refresh();
      if (isCurrent())
        props.notify(
          "Die Sternenkarte wurde aus den Geburtsangaben berechnet.",
        );
    } catch (e) {
      if (isCurrent()) setError((e as Error).message);
    } finally {
      requestLock.current = false;
      if (isCurrent()) setBusy("");
    }
  }
  function download() {
    if (!client.chart) return;
    const url = URL.createObjectURL(
      new Blob([JSON.stringify(client.chart, null, 2)], {
        type: "application/json",
      }),
    );
    const a = document.createElement("a");
    a.href = url;
    a.download = `sense-and-stars-radix-${client.id}.json`;
    a.click();
    URL.revokeObjectURL(url);
  }
  if (!clientMatchesWorkspace(client, props.practice))
    return (
      <ErrorBox error="Diese Sternenkarte gehört nicht zum gewählten Arbeitsbereich." />
    );
  return (
    <>
      <section className="glass-card chart-builder">
        <SectionTitle
          title={
            client.chart
              ? "Deine Sternenkarte vertiefen."
              : "Die persönliche Sternenkarte berechnen."
          }
          eyebrow={client.name}
        />
        {!client.birth_date || !client.birth_time ? (
          <div className="alert">
            <Icon name="note" />
            <span>
              Für die Berechnung fehlen Geburtsdatum oder Geburtszeit. Ergänze
              die Angaben im Klientenprofil.
            </span>
            <button
              className="text-link"
              onClick={() => go("clients/" + client.id)}
            >
              Zum Profil <Icon name="arrow" size={14} />
            </button>
          </div>
        ) : (
          <>
            <div className="birth-summary">
              <span>
                <Icon name="calendar" size={16} />
                {dateFormat(client.birth_date)}
              </span>
              <span>
                <Icon name="clock" size={16} />
                {client.birth_time.slice(0, 5)} Uhr · Ortszeit
              </span>
            </div>
            <form className="place-search" onSubmit={search}>
              <label>
                Geburtsort suchen
                <input
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  required
                  minLength={2}
                  maxLength={180}
                  placeholder="Ort, Region oder Land"
                />
              </label>
              <button className="button secondary" disabled={!!busy}>
                <Icon name="search" size={17} />
                {busy === "search" ? "Suche …" : "Ort suchen"}
              </button>
            </form>
            <p className="field-hint">
              <Icon name="shield" size={13} /> Erst beim Suchen wird
              ausschließlich der Ortsname an den Ortsdienst gesendet.
            </p>
            {places.length > 0 && (
              <fieldset className="place-results">
                <legend>Wähle den passenden Geburtsort ausdrücklich aus</legend>
                {places.map((p) => (
                  <label
                    key={p.id}
                    className={
                      "place-option " + (place?.id === p.id ? "selected" : "")
                    }
                  >
                    <input
                      type="radio"
                      name="place"
                      checked={place?.id === p.id}
                      onChange={() => setPlace(p)}
                    />
                    <span>
                      <strong>{p.label}</strong>
                      <small>
                        {p.timezone} · {p.source}
                      </small>
                    </span>
                    {place?.id === p.id && <Icon name="check" size={18} />}
                  </label>
                ))}
              </fieldset>
            )}
            {place && (
              <div className="chart-options">
                <label>
                  Falls die Geburtszeit zweimal vorkommt
                  <select
                    value={fold}
                    onChange={(e) => setFold(e.target.value)}
                  >
                    <option value="">
                      Automatisch prüfen · bei Mehrdeutigkeit stoppen
                    </option>
                    <option value="0">
                      Erstes Vorkommen (vor Zeitumstellung)
                    </option>
                    <option value="1">
                      Zweites Vorkommen (nach Zeitumstellung)
                    </option>
                  </select>
                  <small>
                    Nur bei einer mehrdeutigen historischen Ortszeit bewusst
                    auswählen.
                  </small>
                </label>
                <button
                  className="button primary blue-button"
                  disabled={!!busy}
                  onClick={() => void calculate()}
                >
                  {busy === "chart"
                    ? "Wird berechnet …"
                    : client.chart
                      ? "Neu berechnen"
                      : "Sternenkarte berechnen"}
                  <Icon name="orbit" size={17} />
                </button>
              </div>
            )}
          </>
        )}
        <ErrorBox error={error} />
      </section>
      {client.chart && (
        <section className="glass-card chart-result">
          <SectionTitle
            title="Der Himmel zum Geburtsmoment"
            eyebrow="PERSÖNLICHES RADIX"
          >
            <div className="button-pair">
              <button
                className="button secondary small"
                onClick={() => setJson(true)}
              >
                JSON ansehen
              </button>
              <button
                className="icon-button"
                onClick={download}
                aria-label="Berechnungsdaten als JSON herunterladen"
              >
                <Icon name="download" size={18} />
              </button>
            </div>
          </SectionTitle>
          <ChartDisplay chart={client.chart} />
        </section>
      )}
      {json && (
        <Modal
          title="Nachvollziehbare Berechnungsdaten"
          description="Planeten, Häuser, Aspekte und Herkunft als strukturiertes JSON."
          onClose={() => setJson(false)}
          wide
        >
          <pre className="json-view">
            {JSON.stringify(client.chart, null, 2)}
          </pre>
          <div className="form-actions">
            <button className="button secondary" onClick={download}>
              <Icon name="download" size={16} /> JSON herunterladen
            </button>
            <button className="button primary" onClick={() => setJson(false)}>
              Schließen
            </button>
          </div>
        </Modal>
      )}
    </>
  );
}
export function ChartDisplay({ chart }: { chart: Chart }) {
  const [tab, setTab] = useState("planets");
  const [view, setView] = useState("radix");
  return (
    <>
      <div className="chart-view-toolbar">
        <div className="segmented" aria-label="Darstellung der Sternenkarte">
          <button
            className={view === "radix" ? "selected" : ""}
            aria-pressed={view === "radix"}
            onClick={() => setView("radix")}
          >
            Radix
          </button>
          <button
            className={view === "body" ? "selected" : ""}
            aria-pressed={view === "body"}
            onClick={() => setView("body")}
          >
            Körperansicht
          </button>
        </div>
        <span>Ein Datensatz · zwei Perspektiven</span>
      </div>
      {view === "body" ? (
        <BodyChart chart={chart} />
      ) : (
        <div className="chart-display">
          <div className="chart-wheel">
            <RadixWheel chart={chart} />
            <p>Astronomische Positionen · keine psychologische Diagnose</p>
          </div>
          <div className="chart-details">
            <div className="ascendant-card">
              <span className="eyebrow">DEIN ASZENDENT</span>
              <h3>{chart.ascendant.sign}</h3>
              <p>
                {chart.ascendant.degree.toFixed(2)}° · {chart.timezone}
              </p>
            </div>
            <div className="segmented chart-segments">
              {[
                ["planets", "Planeten"],
                ["houses", "Häuser"],
                ["aspects", "Aspekte"],
              ].map(([id, label]) => (
                <button
                  key={id}
                  className={tab === id ? "selected" : ""}
                  aria-pressed={tab === id}
                  onClick={() => setTab(id)}
                >
                  {label}
                </button>
              ))}
            </div>
            <div className="chart-table-wrap">
              <table className="chart-table">
                <caption className="visually-hidden">
                  {tab === "planets"
                    ? "Planetenpositionen"
                    : tab === "houses"
                      ? "Häuserpositionen"
                      : "Planetenaspekte"}
                </caption>
                <thead>
                  <tr>
                    {(tab === "planets"
                      ? ["Planet", "Zeichen", "Haus"]
                      : tab === "houses"
                        ? ["Haus", "Zeichen", "Grad"]
                        : ["Verbindung", "Aspekt", "Orbis"]
                    ).map((h) => (
                      <th key={h}>{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {tab === "planets"
                    ? chart.planets.map((p) => (
                        <tr key={p.name}>
                          <td>
                            <span className="planet-glyph">
                              {planetSymbol[p.name] || "•"}
                            </span>
                            {planetNames[p.name] || p.name}
                            {p.retrograde && <sup title="rückläufig"> R</sup>}
                          </td>
                          <td>
                            {p.sign}
                            <small>{p.degree.toFixed(2)}°</small>
                          </td>
                          <td>{p.house}</td>
                        </tr>
                      ))
                    : tab === "houses"
                      ? chart.houses.map((h) => (
                          <tr key={h.house}>
                            <td>{h.house}</td>
                            <td>{h.sign}</td>
                            <td>{h.degree.toFixed(2)}°</td>
                          </tr>
                        ))
                      : chart.aspects.map((a, i) => (
                          <tr key={i}>
                            <td>
                              {planetNames[a.planet1] || a.planet1}
                              <small>
                                {planetNames[a.planet2] || a.planet2}
                              </small>
                            </td>
                            <td>{a.aspect}</td>
                            <td>{a.orb.toFixed(2)}°</td>
                          </tr>
                        ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}
      <div className="chart-provenance">
        <Icon name="shield" size={17} />
        <div>
          <strong>Berechnung & Herkunft</strong>
          <p>
            {chart.timezone} ·{" "}
            {dateFormat(chart.utc_datetime, {
              day: "2-digit",
              month: "2-digit",
              year: "numeric",
              hour: "2-digit",
              minute: "2-digit",
              timeZone: "UTC",
            })}{" "}
            UTC
          </p>
          <p>
            {typeof chart.source === "string"
              ? chart.source
              : [
                  chart.source.engine,
                  chart.source.actual_ephemerides?.join(", "),
                ]
                  .filter(Boolean)
                  .join(" · ")}
            {chart.house_system ? ` · Häuser: ${chart.house_system}` : ""}
          </p>
          <p>
            {chart.coordinates.label || "Gewählter Geburtsort"} ·{" "}
            {chart.coordinates.latitude.toFixed(4)}°{" "}
            {chart.coordinates.latitude >= 0 ? "N" : "S"},{" "}
            {Math.abs(chart.coordinates.longitude).toFixed(4)}°{" "}
            {chart.coordinates.longitude >= 0 ? "O" : "W"}
          </p>
          <details className="calculation-details">
            <summary>Berechnungsdetails & Quellen</summary>
            <p>
              {chart.timezone_source ||
                "Historische Ortszeit aus der serverseitigen Zeitzonendatenbank."}
            </p>
            <p>{chart.coordinates.source}</p>
            {typeof chart.source !== "string" && (
              <>
                <p>
                  {chart.source.engine} {chart.source.version}
                </p>
                {chart.source.reference?.startsWith("https://") && (
                  <p>
                    <a
                      href={chart.source.reference}
                      target="_blank"
                      rel="noopener noreferrer"
                    >
                      Ephemeriden-Dokumentation öffnen
                    </a>
                  </p>
                )}
                <p>{chart.source.license}</p>
              </>
            )}
          </details>
          {chart.warnings?.map((w, i) => (
            <p className="warning" key={i}>
              {w}
            </p>
          ))}
        </div>
      </div>
    </>
  );
}
function RadixWheel({ chart }: { chart: Chart }) {
  const center = 250;
  const asc = chart.ascendant.longitude;
  const xy = (deg: number, r: number) => {
    const a = ((deg - asc) * Math.PI) / 180;
    return { x: center - r * Math.cos(a), y: center + r * Math.sin(a) };
  };
  const planetPoints = chart.planets.map((p, i) => ({
    ...p,
    ...xy(p.longitude, 158 - (i % 3) * 12),
  }));
  return (
    <svg
      viewBox="0 0 500 500"
      role="img"
      aria-labelledby="radix-title radix-desc"
    >
      <title id="radix-title">Persönliches Radix</title>
      <desc id="radix-desc">
        Astronomisch berechnete Planeten, zwölf Tierkreiszeichen und Häuser.
        Genaue Positionen stehen in der Tabelle daneben.
      </desc>
      <defs>
        <radialGradient id="wheel-bg">
          <stop offset="0" stopColor="#fff" stopOpacity=".7" />
          <stop offset="1" stopColor="#efebf5" stopOpacity=".5" />
        </radialGradient>
      </defs>
      <circle
        cx="250"
        cy="250"
        r="231"
        fill="url(#wheel-bg)"
        stroke="#cfc3db"
        strokeWidth=".7"
      />
      {[224, 193, 178, 115].map((r) => (
        <circle
          key={r}
          cx="250"
          cy="250"
          r={r}
          fill="none"
          stroke="#bdb0cd"
          strokeWidth=".65"
          opacity={r === 115 ? 0.35 : 1}
        />
      ))}
      {Array.from({ length: 360 }, (_, i) => {
        const a = xy(i, 224),
          b = xy(i, i % 30 === 0 ? 210 : i % 5 === 0 ? 218 : 221);
        return (
          <line
            key={i}
            x1={a.x}
            y1={a.y}
            x2={b.x}
            y2={b.y}
            stroke="#a799b9"
            strokeWidth={i % 30 === 0 ? 1 : 0.55}
          />
        );
      })}
      {zodiac.map((sign, i) => {
        const a = xy(i * 30, 193),
          b = xy(i * 30, 224),
          t = xy(i * 30 + 15, 207);
        return (
          <g key={sign}>
            <line
              x1={a.x}
              y1={a.y}
              x2={b.x}
              y2={b.y}
              stroke="#b5a6c4"
              strokeWidth=".8"
            />
            <text
              x={t.x}
              y={t.y + 6}
              textAnchor="middle"
              fontSize="20"
              fill={["#9E0000", "#9B59B6", "#3498DB", "#2ECC71"][i % 4]}
            >
              {sign + "\uFE0E"}
            </text>
          </g>
        );
      })}
      {chart.houses.map((h) => {
        const a = xy(h.longitude, 115),
          b = xy(h.longitude, 193),
          t = xy(h.longitude + 8, 184);
        return (
          <g key={h.house}>
            <line
              x1={a.x}
              y1={a.y}
              x2={b.x}
              y2={b.y}
              stroke={h.house === 1 || h.house === 10 ? "#9B59B6" : "#b7aec2"}
              strokeWidth={h.house === 1 || h.house === 10 ? 1.4 : 0.6}
            />
            <text
              x={t.x}
              y={t.y + 3}
              fill="#80708f"
              textAnchor="middle"
              fontSize="9"
            >
              {h.house}
            </text>
          </g>
        );
      })}
      {chart.aspects.slice(0, 35).map((a, i) => {
        const p1 = chart.planets.find((p) => p.name === a.planet1),
          p2 = chart.planets.find((p) => p.name === a.planet2);
        if (!p1 || !p2) return null;
        const first = xy(p1.longitude, 114),
          second = xy(p2.longitude, 114);
        const positive = /trine|sextile|trigon|sextil/i.test(a.aspect);
        return (
          <line
            key={i}
            x1={first.x}
            y1={first.y}
            x2={second.x}
            y2={second.y}
            stroke={positive ? "#3498DB" : "#9E0000"}
            opacity=".32"
            strokeWidth=".65"
          />
        );
      })}
      {planetPoints.map((p) => (
        <g key={p.name}>
          <circle cx={p.x} cy={p.y} r="12" fill="#faf8fc" opacity=".93" />
          <text
            x={p.x}
            y={p.y + 5}
            textAnchor="middle"
            fontSize="20"
            fill="#554366"
          >
            {planetSymbol[p.name] || p.name.slice(0, 2)}
          </text>
        </g>
      ))}
      <text x="8" y="255" fill="#9B59B6" fontSize="10">
        ASC
      </text>
      <circle cx="250" cy="250" r="4" fill="#9B59B6" opacity=".5" />
    </svg>
  );
}
export function PortalPage(props: PageProps) {
  const { data, loading, error } = useData<Portal>("/portal", props.revision);
  if (loading && !data) return <Loading />;
  if (!data) return <ErrorBox error={error} />;
  const upcoming = data.appointments.filter(
    (a) => a.status === "scheduled" || a.status === "in_progress",
  );
  return (
    <>
      <div className="page-heading">
        <div>
          <span className="eyebrow">DEIN PERSÖNLICHER RAUM</span>
          <h1>Schön, dass du da bist, {props.user.name.split(" ")[0]}.</h1>
          <p>Deine Begleitung. Dein Rhythmus. Dein nächster Schritt.</p>
        </div>
        <button className="button secondary" onClick={() => go("calendar")}>
          <Icon name="plus" size={17} /> Termin buchen
        </button>
      </div>
      <ErrorBox error={error} />
      <div className="portal-hero connection-card">
        <div className="connection-copy">
          <span className="eyebrow">GANZ BEI DIR</span>
          <h2>
            Dein Weg darf sich
            <br />
            <em>nach dir anfühlen.</em>
          </h2>
          <p>
            Hier findest du die Impulse, die deine Beraterin
            <br />
            bewusst mit dir geteilt hat.
          </p>
          <button className="button light" onClick={() => go("calendar")}>
            Deine nächste Begegnung planen <Icon name="arrow" size={17} />
          </button>
        </div>
        <OrbitArt />
      </div>
      <div className="portal-grid">
        <section className="glass-card">
          <SectionTitle
            title="Deine nächsten Begegnungen"
            eyebrow="ZEIT FÜR DICH"
          >
            <button className="text-link" onClick={() => go("calendar")}>
              Alle Termine <Icon name="arrow" size={15} />
            </button>
          </SectionTitle>
          {upcoming.length ? (
            upcoming
              .slice(0, 2)
              .map((a) => <AppointmentRow key={a.id} appointment={a} client />)
          ) : (
            <Empty
              icon="calendar"
              title="Finde Zeit für deinen nächsten Schritt."
              action={
                <button
                  className="button secondary"
                  onClick={() => go("calendar")}
                >
                  Termin buchen
                </button>
              }
            />
          )}
        </section>
        <section className="glass-card portal-privacy">
          <span className="card-icon heart">
            <Icon name="heart" />
          </span>
          <h2>Ein geschützter Ort.</h2>
          <p>
            Hier ist nur deine eigene Begleitung sichtbar. Deine Beraterin
            entscheidet bewusst, welche Impulse sie mit dir teilt.
          </p>
          <Badge tone="green">
            <Icon name="lock" size={12} /> Dein persönlicher Zugang
          </Badge>
        </section>
      </div>
      <section
        className="glass-card resources-panel"
        data-tour="portal-resources"
      >
        <SectionTitle
          title="Impulse für deinen Weg"
          eyebrow="ZWISCHEN DEN BEGEGNUNGEN"
        />
        {data.resources.length ? (
          <div className="resource-list">
            {data.resources.map((r) => (
              <ResourceCard {...props} key={r.id} resource={r} readOnly />
            ))}
          </div>
        ) : (
          <Empty icon="leaf" title="Dein Raum darf sich füllen.">
            Sobald deine Beraterin Impulse mit dir teilt, findest du sie hier.
          </Empty>
        )}
      </section>
      {data.client.chart && (
        <section className="glass-card chart-result" data-tour="portal-chart">
          <SectionTitle
            title="Deine persönliche Sternenkarte"
            eyebrow="EIN REFLEXIONSRAUM"
          />
          <ChartDisplay chart={data.client.chart} />
        </section>
      )}
      <p className="portal-disclaimer">
        <Icon name="shield" size={16} /> Spirituelle Reflexion ergänzt deinen
        persönlichen Weg. Sie ersetzt keine medizinische oder
        psychotherapeutische Beratung.
      </p>
    </>
  );
}
