import {
  useEffect,
  useLayoutEffect,
  useRef,
  useState,
  type FormEvent,
} from "react";
import { api, ApiError, roleName } from "./api";
import { AuthLayout } from "./AuthLayout";
import { PasswordRecovery } from "./PasswordRecovery";
import {
  DedicationDialog,
  DedicationNotice,
  DedicationSettings,
} from "./Dedication";
import {
  useDedication,
  useOtherDialogOpen,
  type DedicationController,
} from "./useDedication";
import { dedicationBlocksTour } from "./dedicationState";
import { captureRecoveryLink, type RecoveryLink } from "./recoveryLink";
import type { DeploymentMode, Health, User } from "./types";
import { go, useRequestScope, useRoute } from "./hooks";
import {
  Avatar,
  Badge,
  Brand,
  ErrorBox,
  Icon,
  Loading,
  Modal,
  type IconName,
} from "./ui";
import {
  DashboardPage,
  CalendarPage,
  ClientsPage,
  ClientPage,
  AstroPage,
  PortalPage,
} from "./Practice";
import { LearningPage, AdminPage } from "./Learning";
import { HelpPage, ContextHelp } from "./Help";
import { parseWorkspaceRoute } from "./practiceMode";
import { euroToCents } from "./pricing";
export type Notify = (message: string) => void;
export interface PageProps {
  user: User;
  revision: number;
  refresh: () => void;
  notify: Notify;
  practice?: boolean;
  mode: DeploymentMode;
}
function safeHttpsUrl(value: string | null | undefined) {
  if (!value) return null;
  try {
    const url = new URL(value);
    return url.protocol === "https:" && !url.username && !url.password
      ? url.toString()
      : null;
  } catch {
    return null;
  }
}
export default function App({
  initialRecoveryLink = null,
}: {
  initialRecoveryLink?: RecoveryLink | null;
}) {
  const [user, setUser] = useState<User | null>(null),
    [checking, setChecking] = useState(true),
    [revision, setRevision] = useState(0),
    [message, setMessage] = useState(""),
    [tour, setTour] = useState(false),
    [mobile, setMobile] = useState(false),
    [offline, setOffline] = useState(!navigator.onLine),
    [mode, setMode] = useState<DeploymentMode>("local"),
    [sourceUrl, setSourceUrl] = useState<string | null>(null);
  const [recoveryLink, setRecoveryLink] = useState(initialRecoveryLink);
  const [recoveryEmail, setRecoveryEmail] = useState("");
  const [recoveryRevision, setRecoveryRevision] = useState(0);
  const [authRevision, setAuthRevision] = useState(0);
  const [authNotice, setAuthNotice] = useState("");
  // Register before useRoute so subsequent reset links are scrubbed before routing.
  useLayoutEffect(() => {
    const capture = () => {
      setRecoveryLink(captureRecoveryLink(window.location, window.history));
      setRecoveryRevision((value) => value + 1);
    };
    window.addEventListener("hashchange", capture);
    return () => window.removeEventListener("hashchange", capture);
  }, []);
  const fullRoute = useRoute();
  const { practice, route } = parseWorkspaceRoute(fullRoute);
  const recoveryActive =
    !!recoveryLink ||
    fullRoute === "reset-password" ||
    fullRoute === "forgot-password";
  const dedication = useDedication(
    user && !recoveryActive ? `${user.id}:${authRevision}` : null,
  );
  const otherDialogOpen = useOtherDialogOpen();
  useEffect(() => {
    if (dedication.state.status !== "expired") return;
    setUser(null);
    setTour(false);
    setAuthNotice(
      "Deine Anmeldung ist abgelaufen. Bitte melde dich erneut an.",
    );
    go("home", false);
  }, [dedication.state.status]);
  useEffect(() => {
    let active = true;
    api<Health>("/health")
      .then((value) => {
        if (!active) return;
        setMode(value.mode);
        setSourceUrl(safeHttpsUrl(value.source_url));
      })
      .catch(() => {});
    api<User>("/auth/me")
      .then((u) => {
        if (!active) return;
        setUser(u);
        setAuthRevision((value) => value + 1);
        setTour(!u.tour_completed);
      })
      .catch(() => {})
      .finally(() => {
        if (active) setChecking(false);
      });
    const online = () => setOffline(!navigator.onLine);
    window.addEventListener("online", online);
    window.addEventListener("offline", online);
    return () => {
      active = false;
      window.removeEventListener("online", online);
      window.removeEventListener("offline", online);
    };
  }, []);
  useEffect(() => {
    setMobile(false);
  }, [fullRoute]);
  useEffect(() => {
    if (!mobile) return;
    const closeNavigation = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setMobile(false);
        document.querySelector<HTMLButtonElement>(".mobile-toggle")?.focus();
      }
    };
    document.addEventListener("keydown", closeNavigation);
    return () => document.removeEventListener("keydown", closeNavigation);
  }, [mobile]);
  useEffect(() => {
    if (message) {
      const id = setTimeout(() => setMessage(""), 5500);
      return () => clearTimeout(id);
    }
  }, [message]);
  const props: PageProps = {
    user: user!,
    revision,
    practice,
    mode,
    refresh: () => setRevision((r) => r + 1),
    notify: setMessage,
  };
  async function logout() {
    try {
      await api("/auth/logout", {});
      setAuthNotice("");
      setUser(null);
      setTour(false);
      go("home", false);
    } catch (error) {
      setMessage((error as Error).message);
    }
  }
  if (checking)
    return (
      <div className="full-loading">
        <Brand className="full-loading-brand" tagline={false} />
        <Loading />
      </div>
    );
  if (recoveryActive)
    return (
      <PasswordRecovery
        key={`${fullRoute === "forgot-password" ? "request" : "reset"}-${recoveryRevision}`}
        link={
          fullRoute === "forgot-password"
            ? null
            : recoveryLink || { token: null }
        }
        initialEmail={recoveryEmail}
        offline={offline}
        sourceUrl={sourceUrl}
        onRequestNew={() => {
          setRecoveryLink(null);
          go("forgot-password", false);
        }}
        onPasswordChanged={() => {
          setUser(null);
          setTour(false);
          setRecoveryLink({ token: null });
        }}
        onBack={() => {
          setRecoveryLink(null);
          setUser(null);
          setTour(false);
          go("home", false);
        }}
      />
    );
  if (!user)
    return (
      <Login
        offline={offline}
        sourceUrl={sourceUrl}
        notice={authNotice}
        onForgot={(email) => {
          setRecoveryEmail(email);
          go("forgot-password", false);
        }}
        onLogin={(u) => {
          setAuthNotice("");
          setUser(u);
          setAuthRevision((value) => value + 1);
          setTour(!u.tour_completed);
          go("home", false);
        }}
      />
    );
  const isClient = user.role === "client";
  const nav: { id: string; label: string; icon: IconName; tone: string }[] =
    isClient
      ? [
          { id: "home", label: "Mein Raum", icon: "home", tone: "root" },
          {
            id: "calendar",
            label: "Meine Termine",
            icon: "calendar",
            tone: "sacral",
          },
        ]
      : [
          { id: "home", label: "Übersicht", icon: "home", tone: "root" },
          {
            id: "calendar",
            label: "Kalender",
            icon: "calendar",
            tone: "sacral",
          },
          { id: "clients", label: "Klienten", icon: "users", tone: "root" },
          { id: "astro", label: "Sternenkarte", icon: "orbit", tone: "throat" },
          {
            id: "learning",
            label: "Lernraum",
            icon: "book",
            tone: "third-eye",
          },
        ];
  const active = route.split("/")[0];
  const current = nav.find((n) => n.id === active);
  let page;
  if (active === "help" && !isClient) page = <HelpPage />;
  else if (active === "settings")
    page = (
      <Settings
        user={user}
        restart={() => setTour(true)}
        logout={logout}
        mode={mode}
        dedication={dedication}
        onSaved={(updated) =>
          setUser((current) => (current?.id === updated.id ? updated : current))
        }
      />
    );
  else if (active === "learning" && !isClient)
    page = <LearningPage {...props} />;
  else if (active === "admin" && user.role === "admin")
    page = <AdminPage {...props} />;
  else if (active === "calendar") page = <CalendarPage {...props} />;
  else if (isClient) page = <PortalPage {...props} />;
  else if (active === "clients" && route.split("/")[1])
    page = <ClientPage {...props} id={Number(route.split("/")[1])} />;
  else if (active === "clients") page = <ClientsPage {...props} />;
  else if (active === "astro") page = <AstroPage {...props} />;
  else page = <DashboardPage {...props} />;
  return (
    <div className={"app " + (mobile ? "mobile-open" : "")}>
      <a
        className="skip-link"
        href="#main-content"
        onClick={(event) => {
          event.preventDefault();
          document.getElementById("main-content")?.focus();
        }}
      >
        Zum Inhalt
      </a>
      {mobile && (
        <button
          className="sidebar-backdrop"
          aria-label="Navigation schließen"
          onClick={() => setMobile(false)}
        />
      )}
      <aside className="sidebar" aria-label="Hauptnavigation">
        <a
          className="brand-link"
          href={"#" + (practice ? "practice/" : "") + "home"}
          aria-label="Sense & Stars – Startseite"
        >
          <Brand />
        </a>
        <div className="workspace-label">
          <span className="status-dot" />{" "}
          {isClient ? "Dein persönlicher Raum" : "Dein Praxisraum"}
        </div>
        <nav>
          {nav.map((item) => (
            <a
              key={item.id}
              data-tour={item.id}
              href={"#" + (practice ? "practice/" : "") + item.id}
              className={"nav-link " + (active === item.id ? "active" : "")}
              aria-current={active === item.id ? "page" : undefined}
              style={
                {
                  "--nav-tone": `var(--chakra-${item.tone})`,
                } as React.CSSProperties
              }
            >
              <Icon name={item.icon} />
              <span>{item.label}</span>
              {active === item.id && <span className="nav-active-dot" />}
            </a>
          ))}
        </nav>
        <div className="sidebar-bottom">
          <div className="mindful-note">
            <Icon name="leaf" />
            <p>
              Entwicklung beginnt
              <br />
              mit einem Moment Präsenz.
            </p>
            <span className="mini-chakras">
              {[
                "root",
                "sacral",
                "solar",
                "heart",
                "throat",
                "third-eye",
                "crown",
              ].map((t) => (
                <i key={t} style={{ background: `var(--chakra-${t})` }} />
              ))}
            </span>
          </div>
          {!isClient && (
            <a
              className={"nav-link " + (active === "help" ? "active" : "")}
              href={"#" + (practice ? "practice/" : "") + "help"}
            >
              <Icon name="help" />
              <span>Hilfe & Anleitungen</span>
            </a>
          )}
          {user.role === "admin" && (
            <a
              className={"nav-link " + (active === "admin" ? "active" : "")}
              href={"#" + (practice ? "practice/" : "") + "admin"}
            >
              <Icon name="note" />
              <span>Inhalte verwalten</span>
            </a>
          )}
          <a
            className={"nav-link " + (active === "settings" ? "active" : "")}
            href={"#" + (practice ? "practice/" : "") + "settings"}
          >
            <Icon name="settings" />
            <span>Einstellungen</span>
          </a>
          <button className="user-block" onClick={() => go("settings")}>
            <Avatar name={user.name} />
            <span>
              <strong>{user.name}</strong>
              <small>{roleName(user.role)}</small>
            </span>
            <Icon name="chevron" size={16} />
          </button>
        </div>
      </aside>
      <div className="app-body">
        <header className="topbar">
          <div className="topbar-left">
            <button
              className="icon-button mobile-toggle"
              aria-label="Navigation öffnen"
              aria-expanded={mobile}
              onClick={() => setMobile(!mobile)}
            >
              <Icon name="menu" />
            </button>
            <span className="breadcrumb">
              Dein Raum <Icon name="chevron" size={12} />
              <strong>
                {current?.label ||
                  (active === "settings"
                    ? "Einstellungen"
                    : active === "help"
                      ? "Hilfe & Anleitungen"
                      : active === "admin"
                        ? "Inhalte verwalten"
                        : "Übersicht")}
              </strong>
            </span>
          </div>
          <div className="topbar-right">
            {!isClient && (
              <div className="workspace-switch" aria-label="Arbeitsbereich">
                <a
                  href={
                    "#" + (route.startsWith("clients/") ? "clients" : route)
                  }
                  aria-current={!practice ? "true" : undefined}
                  className={!practice ? "selected" : ""}
                >
                  Praxis
                </a>
                <a
                  href={
                    "#practice/" +
                    (route.startsWith("clients/") ? "clients" : route)
                  }
                  aria-current={practice ? "true" : undefined}
                  className={practice ? "selected" : ""}
                >
                  Üben
                </a>
              </div>
            )}
            {!isClient && (
              <button
                className="icon-button"
                aria-label="Hilfe und Anleitungen öffnen"
                title="Wie war das noch einmal?"
                onClick={() => go("help")}
              >
                <Icon name="help" />
              </button>
            )}
            <Badge tone="demo">
              <span className="status-dot" />{" "}
              {mode === "demo"
                ? "Demo · synthetische Daten"
                : mode === "hosted"
                  ? "Online · geschützter Raum"
                  : "Lokal · geschützter Raum"}
            </Badge>
            <button
              className="icon-button tour-trigger"
              title="App-Tour öffnen"
              aria-label="App-Tour öffnen"
              onClick={() => setTour(true)}
            >
              <Icon name="spark" />
            </button>
            <button
              className="header-avatar"
              onClick={() => go("settings")}
              aria-label="Mein Konto öffnen"
            >
              <Avatar name={user.name} size="small" />
            </button>
          </div>
        </header>
        {offline && (
          <div className="offline-banner" role="status">
            <Icon name="lock" size={16} /> Offline: Die App-Hülle ist verfügbar.
            Geschützte Daten benötigen{" "}
            {mode === "hosted" ? "die" : "den lokalen"} Server
            {mode === "hosted" ? "verbindung" : ""}.
          </div>
        )}
        {!isClient && practice && (
          <div className="practice-banner" role="status">
            <Icon name="users" size={18} />
            <span>
              <strong>Übungsmodus</strong> · Du arbeitest mit deinen eigenen
              fiktiven Testpersonen.
            </span>
            <ContextHelp topic="practice" />
          </div>
        )}
        {!offline && <DedicationNotice controller={dedication} />}
        <main
          id="main-content"
          className="main-content"
          tabIndex={-1}
          key={
            (practice ? "practice/" : "") +
            (active === "clients" ? route : active)
          }
        >
          {offline && (
            <div className="offline-locked glass-card">
              <Icon name="lock" size={30} />
              <h2>Dein Raum ist geschützt.</h2>
              <p>
                Geschützte Inhalte werden offline ausgeblendet. Verbinde dich
                wieder mit dem Server. Ungespeicherte Eingaben bleiben in diesem
                geöffneten Fenster erhalten.
              </p>
            </div>
          )}
          <div
            hidden={offline}
            aria-hidden={offline}
            style={{ display: offline ? "none" : "contents" }}
          >
            {page}
          </div>
        </main>
        <footer className="app-footer">
          <span>
            Sense &amp; Stars <span aria-hidden="true">·</span> Mit Achtsamkeit
            verbunden.
          </span>
          {sourceUrl && (
            <a
              className="text-link"
              href={sourceUrl}
              target="_blank"
              rel="noopener noreferrer"
              aria-label="Quellcode von Sense & Stars unter der AGPL öffnen"
            >
              Quellcode · AGPL
            </a>
          )}
          <span>
            <Icon name="shield" size={13} />{" "}
            {mode === "hosted"
              ? "Online & geschützt"
              : mode === "demo"
                ? "Lokale Demo & geschützt"
                : "Lokal & geschützt"}
          </span>
        </footer>
      </div>
      {message && (
        <div className="toast" role="status">
          <Icon name="check" />
          <span>{message}</span>
          <button
            className="icon-button"
            aria-label="Hinweis schließen"
            onClick={() => setMessage("")}
          >
            <Icon name="close" size={16} />
          </button>
        </div>
      )}
      {dedication.state.open &&
        dedication.state.dedication &&
        !otherDialogOpen && (
          <DedicationDialog
            key={`${dedication.state.dedication.id}:${dedication.state.dedication.version}`}
            letter={dedication.state.dedication}
            onClose={() => void dedication.dismiss()}
          />
        )}
      {tour && !dedicationBlocksTour(dedication.state) && !otherDialogOpen && (
        <Tour
          user={user}
          onClose={() => setTour(false)}
          onDone={(u) => {
            setUser(u);
            setTour(false);
          }}
        />
      )}
    </div>
  );
}
function Login({
  onLogin,
  offline,
  sourceUrl,
  onForgot,
  notice,
}: {
  onLogin: (user: User) => void;
  offline: boolean;
  sourceUrl: string | null;
  onForgot: (email: string) => void;
  notice: string;
}) {
  const active = useRef(true);
  const heading = useRef<HTMLHeadingElement>(null);
  const [email, setEmail] = useState(""),
    [password, setPassword] = useState(""),
    [error, setError] = useState(""),
    [locked, setLocked] = useState(false),
    [busy, setBusy] = useState(false),
    [demo, setDemo] = useState<{
      accounts: {
        name: string;
        email: string;
        password: string;
        role: string;
      }[];
      notice: string;
    } | null>(null);
  useEffect(() => {
    active.current = true;
    heading.current?.focus();
    api<{
      accounts: {
        name: string;
        email: string;
        password: string;
        role: string;
      }[];
      notice: string;
    }>("/demo")
      .then((value) => {
        if (active.current) setDemo(value);
      })
      .catch(() => {});
    return () => {
      active.current = false;
    };
  }, []);
  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    setLocked(false);
    try {
      const authenticated = await api<User>("/auth/login", { email, password });
      if (!active.current) return;
      onLogin(authenticated);
      setPassword("");
    } catch (error) {
      if (!active.current) return;
      const rateLimited = error instanceof ApiError && error.status === 429;
      setLocked(rateLimited);
      setError(
        rateLimited
          ? "Die Anmeldung ist nach mehreren Versuchen vorübergehend gesperrt. Bitte warte bis zu zehn Minuten oder setze dein Passwort zurück."
          : (error as Error).message,
      );
    } finally {
      if (active.current) setBusy(false);
    }
  }
  return (
    <AuthLayout sourceUrl={sourceUrl}>
      <span className="welcome-icon">
        <Icon name="sun" size={28} />
      </span>
      <span className="eyebrow">WILLKOMMEN IN DEINEM RAUM</span>
      <h2 ref={heading} tabIndex={-1} className="auth-heading">
        Schön, dass du da bist.
      </h2>
      <p>Melde dich an und komm in Ruhe an.</p>
      {notice && (
        <div className="alert" role="status">
          {notice}
        </div>
      )}
      {offline && (
        <div className="alert" role="status">
          Du bist offline. Die App-Hülle ist bereit; für die Anmeldung und deine
          geschützten Inhalte benötigst du wieder eine Verbindung.
        </div>
      )}
      <form onSubmit={submit}>
        <label>
          E-Mail-Adresse
          <input
            type="email"
            name="email"
            autoComplete="username"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="dein.name@beispiel.de"
          />
        </label>
        <label>
          Passwort
          <input
            type="password"
            name="password"
            autoComplete="current-password"
            required
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder="Dein persönliches Passwort"
          />
        </label>
        <ErrorBox error={error} />
        <button className="button primary login-button" disabled={busy}>
          {busy ? "Dein Raum öffnet sich …" : "Meinen Raum öffnen"}
          <Icon name="arrow" size={18} />
        </button>
      </form>
      <button
        className="button text auth-forgot"
        type="button"
        onClick={() => onForgot(email)}
      >
        Passwort vergessen?
      </button>
      {locked && (
        <p className="auth-field-help" role="status">
          Du kannst auch während der Anmeldepause einen Link zum Zurücksetzen
          anfordern.
        </p>
      )}
      {demo && (
        <details className="demo-access">
          <summary>
            Lokale Demo entdecken <Badge>Testzugänge</Badge>
          </summary>
          <p>
            {demo.notice ||
              "Ausschließlich synthetische Beispieldaten. Die Zugangsdaten werden bei der Einrichtung lokal erzeugt."}
          </p>
          <div>
            {demo.accounts.map((account) => (
              <button
                type="button"
                className="demo-account"
                key={account.email}
                onClick={() => {
                  setEmail(account.email);
                  setPassword(account.password);
                  setError("");
                }}
              >
                <span>
                  <strong>{account.name}</strong>
                  <small>{roleName(account.role)}</small>
                </span>
                <Icon name="arrow" size={16} />
              </button>
            ))}
          </div>
        </details>
      )}
    </AuthLayout>
  );
}
function Tour({
  user,
  onDone,
}: {
  user: User;
  onClose: () => void;
  onDone: (u: User) => void;
}) {
  const [step, setStep] = useState(0),
    [busy, setBusy] = useState(false),
    [error, setError] = useState("");
  const heading = useRef<HTMLHeadingElement>(null);
  const client = user.role === "client";
  const steps = client
    ? [
        {
          icon: "home" as IconName,
          title: "Dein Raum. Dein Rhythmus.",
          text: "Hier findest du deine nächsten Termine und alles, was deine Beraterin bewusst mit dir teilt.",
          detail: "Nur deine eigene Begleitung ist für dich sichtbar.",
          route: "home",
          target: "home",
        },
        {
          icon: "heart" as IconName,
          title: "Impulse, die dich weiterbegleiten.",
          text: "Freigegebene Notizen, persönliche Aufgaben und Audio-Links begleiten dich zwischen den Begegnungen.",
          detail:
            "Die Freigabe für jedes einzelne Element liegt bewusst bei deiner Beraterin.",
          route: "home",
          target: "portal-resources",
        },
        {
          icon: "orbit" as IconName,
          title: "Ein Blick auf deine Sternenkarte.",
          text: "Wenn deine Beraterin deine Karte freigibt, kannst du sie hier in deinem eigenen Raum entdecken.",
          detail:
            "Astrologie ist ein spirituelles Reflexionsmodell und keine Diagnose.",
          route: "home",
          target: "portal-chart",
        },
        {
          icon: "calendar" as IconName,
          title: "Zeit für deinen nächsten Schritt.",
          text: "In deinen Terminen findest du deine nächste Begegnung. Wähle einen freien Zeitraum und buche ihn direkt.",
          detail: "Die Buchung löst keine Zahlung oder Nachricht aus.",
          route: "calendar",
          target: "calendar",
        },
      ]
    : [
        {
          icon: "home" as IconName,
          title: "Alles beginnt mit Ankommen.",
          text: "Deine Übersicht verbindet deine Klienten und die kommenden Sitzungen. Im Kalender planst du neue Begegnungen.",
          detail: "Ein ruhiger Ausgangspunkt für deinen Praxistag.",
          route: "home",
          target: "home",
        },
        {
          icon: "orbit" as IconName,
          title: "Ein neuer Blick auf Menschen.",
          text: "Lege einen Klienten an, wähle den Geburtsort und berechne seine persönliche Sternenkarte.",
          detail:
            "Ortszeit, Zeitzone und Berechnungsquelle bleiben nachvollziehbar.",
          route: "astro",
          target: "astro",
        },
        {
          icon: "book" as IconName,
          title: "Dein Wissen darf wachsen.",
          text: "Wähle deinen Einstieg frei. Entdecke Grundlagen und Vertiefungen, merke wichtige Kapitel und halte eigene Erkenntnisse im privaten Notizbuch fest.",
          detail:
            "Neue Inhalte bleiben Entwürfe bis zur bewussten Admin-Freigabe.",
          route: "learning",
          target: "learning",
        },
        {
          icon: "heart" as IconName,
          title: "Mit Empathie bewusst begleiten.",
          text: "Öffne vor jeder Sitzung den Schutzraum: komme an, prüfe Grenzen und Vertraulichkeit und bestätige den Rahmen ausdrücklich.",
          detail:
            "Erst nach dieser Bestätigung kann eine zeitlich passende Sitzung beginnen.",
          route: "calendar",
          target: "protection",
        },
      ];
  const current = steps[step];
  useEffect(() => {
    go(current.route);
    const timer = window.setTimeout(() => {
      const target =
        document.querySelector(`[data-tour="${current.target}"]`) ||
        document.querySelector('[data-tour="home"]');
      target?.classList.add("tour-highlight");
      heading.current?.focus();
    }, 100);
    return () => {
      window.clearTimeout(timer);
      document
        .querySelectorAll(".tour-highlight")
        .forEach((node) => node.classList.remove("tour-highlight"));
    };
  }, [step, client, current.route, current.target]);
  async function finish() {
    setBusy(true);
    setError("");
    try {
      const updated = await api<User>(
        "/auth/me",
        { tour_completed: true },
        "PATCH",
      );
      go("home");
      onDone(updated);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <Modal
      title="Willkommen bei Sense & Stars"
      className="tour-modal"
      onClose={() => {
        if (!busy) void finish();
      }}
    >
      <div className="tour">
        <div className="tour-visual">
          <span className="tour-orbit">
            <Icon name={current.icon} size={38} />
          </span>
          <div className="tour-constellation" aria-hidden="true">
            ✧
          </div>
        </div>
        <span className="eyebrow">DEIN ERSTER RUNDGANG · {step + 1} VON 4</span>
        <h3 ref={heading} key={step} tabIndex={-1}>
          {current.title}
        </h3>
        <p>{current.text}</p>
        <div className="tour-detail">
          <Icon name="shield" size={16} />
          {current.detail}
        </div>
        <ErrorBox error={error} />
        <div className="tour-progress" aria-label={`Schritt ${step + 1} von 4`}>
          {steps.map((_, i) => (
            <span
              key={i}
              className={i === step ? "active" : i < step ? "done" : ""}
            />
          ))}
        </div>
        <div className="form-actions">
          <button
            className="button text"
            disabled={busy}
            onClick={() => {
              if (step > 0) setStep(step - 1);
              else void finish();
            }}
          >
            {step > 0 ? "Zurück" : "Tour überspringen"}
          </button>
          <button
            className="button primary"
            disabled={busy}
            onClick={() => {
              if (step < 3) setStep(step + 1);
              else void finish();
            }}
          >
            {busy
              ? "Wird gespeichert …"
              : step === 3
                ? "Meinen Raum entdecken"
                : "Weiter"}
            <Icon name="arrow" size={17} />
          </button>
        </div>
      </div>
    </Modal>
  );
}
function Settings({
  user,
  restart,
  logout,
  mode,
  onSaved,
  dedication,
}: {
  user: User;
  restart: () => void;
  logout: () => void;
  mode: DeploymentMode;
  onSaved: (user: User) => void;
  dedication: DedicationController;
}) {
  const isCurrent = useRequestScope();
  const [name, setName] = useState(user.name);
  const [rate, setRate] = useState(
    user.hourly_rate_cents == null
      ? ""
      : (user.hourly_rate_cents / 100).toFixed(2),
  );
  const [busy, setBusy] = useState(false);
  const [saved, setSaved] = useState("");
  const [error, setError] = useState("");
  const lock = useRef(false);
  async function saveProfile(event: FormEvent) {
    event.preventDefault();
    if (lock.current) return;
    setError("");
    setSaved("");
    try {
      const trimmedName = name.trim();
      if (!trimmedName) throw new Error("Bitte gib deinen Anzeigenamen ein.");
      const payload = {
        name: trimmedName,
        ...(user.role !== "client"
          ? { hourly_rate_cents: euroToCents(rate) }
          : {}),
      };
      lock.current = true;
      setBusy(true);
      const updated = await api<User>("/auth/me", payload, "PATCH");
      if (updated.id !== user.id) return;
      onSaved(updated);
      if (!isCurrent()) return;
      setName(updated.name);
      setRate(
        updated.hourly_rate_cents == null
          ? ""
          : (updated.hourly_rate_cents / 100).toFixed(2),
      );
      setSaved(
        "Dein Profil ist gespeichert. Bereits vereinbarte Sitzungspreise bleiben erhalten.",
      );
    } catch (e) {
      if (isCurrent()) setError((e as Error).message);
    } finally {
      lock.current = false;
      if (isCurrent()) setBusy(false);
    }
  }
  return (
    <>
      <div className="page-heading">
        <span className="eyebrow">GANZ BEI DIR</span>
        <h1>Dein Raum, dein Zugang.</h1>
        <p>Persönliches Konto und Orientierung für deinen Alltag.</p>
      </div>
      <div className="settings-grid">
        <section className="glass-card settings-card">
          <span className="card-icon crown">
            <Icon name="users" />
          </span>
          <h2>Dein Profil</h2>
          <div className="profile-line">
            <Avatar name={user.name} size="large" />
            <div>
              <h3>{user.name}</h3>
              <p>{user.email}</p>
              <Badge>{roleName(user.role)}</Badge>
            </div>
          </div>
          <form className="profile-settings-form" onSubmit={saveProfile}>
            <label>
              Anzeigename
              <input
                name="display_name"
                value={name}
                onChange={(event) => setName(event.target.value)}
                maxLength={120}
                required
                readOnly={busy}
                autoComplete="name"
              />
              <small>So begrüßt dich deine Übersicht.</small>
            </label>
            {user.role !== "client" && (
              <label>
                Stundensatz in €
                <input
                  name="hourly_rate"
                  inputMode="decimal"
                  value={rate}
                  onChange={(event) => setRate(event.target.value)}
                  readOnly={busy}
                  placeholder="Noch nicht festgelegt"
                />
                <small>
                  Für neue Termine: Stundensatz × Dauer. Leer bedeutet ohne
                  Standardpreis. Einzelne Sitzungspreise kannst du beim Anlegen
                  anpassen.
                </small>
              </label>
            )}
            <ErrorBox error={error} />
            {saved && (
              <p className="workspace-feedback" role="status">
                {saved}
              </p>
            )}
            <button className="button primary" disabled={busy}>
              {busy ? "Wird gespeichert …" : "Profil speichern"}
              <Icon name="check" size={17} />
            </button>
          </form>
          <button className="button secondary" onClick={logout}>
            <Icon name="logout" size={17} /> Sicher abmelden
          </button>
        </section>
        <section className="glass-card settings-card">
          <span className="card-icon crown">
            <Icon name="spark" />
          </span>
          <h2>Wieder einen Überblick finden.</h2>
          <p>
            Die App-Tour zeigt dir in vier ruhigen Schritten die wichtigsten
            Abläufe.
          </p>
          <button className="button secondary" onClick={restart}>
            App-Tour wiederholen <Icon name="arrow" size={17} />
          </button>
        </section>
        <DedicationSettings controller={dedication} />
        <section className="glass-card settings-card wide">
          <span className="card-icon heart">
            <Icon name="shield" />
          </span>
          <h2>Ein bewusster Rahmen.</h2>
          {mode === "hosted" ? (
            <p>
              Sense &amp; Stars wird online bereitgestellt. Klientenakten,
              Termine und Sitzungen werden dort serverseitig gespeichert und
              verarbeitet. Die Offline-Funktion speichert nur öffentliche
              App-Dateien; geschützte Inhalte werden nicht im Offline-Cache
              abgelegt.
            </p>
          ) : (
            <p>
              Sense &amp; Stars läuft lokal. Die Offline-Funktion speichert nur
              öffentliche App-Dateien. Klientenakten, Termine und Sitzungen
              werden nicht im Offline-Cache abgelegt.
            </p>
          )}
          <p>
            {mode === "demo"
              ? "Diese Demo verwendet ausschließlich synthetische Daten. "
              : ""}
            Echter Betrieb benötigt eine eigene Prüfung von Datenschutz,
            Datensicherung, Hosting und fachlichen Inhalten.
          </p>
          <p className="fineprint">
            Astrologie ist ein spirituelles Reflexionsmodell. Sie ist keine
            Diagnose, Behandlung oder nachgewiesene Therapie.
          </p>
        </section>
      </div>
    </>
  );
}
