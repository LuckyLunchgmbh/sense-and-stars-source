import { useEffect, useRef, useState, type FormEvent } from "react";
import { api, ApiError } from "./api";
import { AuthLayout } from "./AuthLayout";
import { Icon } from "./ui";
import {
  recoveryRequestError,
  validateRecoveryPassword,
  type RecoveryLink,
} from "./recoveryLink";

const unavailableMessage =
  "Das Zurücksetzen per E-Mail ist technisch noch nicht eingerichtet. Bitte kontaktiere die Person, die deinen Zugang eingerichtet hat. Es wurde keine E-Mail verschickt.";

export function PasswordRecovery({
  link,
  initialEmail,
  offline,
  sourceUrl,
  onRequestNew,
  onPasswordChanged,
  onBack,
}: {
  link: RecoveryLink | null;
  initialEmail: string;
  offline: boolean;
  sourceUrl: string | null;
  onRequestNew: () => void;
  onPasswordChanged: () => void;
  onBack: () => void;
}) {
  const [email, setEmail] = useState(initialEmail);
  const [password, setPassword] = useState("");
  const [confirmation, setConfirmation] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [available, setAvailable] = useState<boolean | null>(null);
  const [availabilityFailed, setAvailabilityFailed] = useState(false);
  const [availabilityRevision, setAvailabilityRevision] = useState(0);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [requestMessage, setRequestMessage] = useState("");
  const [invalidLink, setInvalidLink] = useState(false);
  const [changed, setChanged] = useState(false);
  const heading = useRef<HTMLHeadingElement>(null);
  const feedback = useRef<HTMLDivElement>(null);
  const active = useRef(true);
  const resetting = link !== null;
  const missingToken = resetting && (!link.token || invalidLink);

  useEffect(() => {
    active.current = true;
    return () => {
      active.current = false;
    };
  }, []);
  useEffect(() => {
    heading.current?.focus();
  }, [resetting, changed]);
  useEffect(() => {
    if (error || requestMessage) feedback.current?.focus();
  }, [error, requestMessage]);
  useEffect(() => {
    if (resetting) return;
    let current = true;
    setAvailable(null);
    setAvailabilityFailed(false);
    api<{ available: boolean }>("/auth/recovery")
      .then((value) => {
        if (current) setAvailable(value.available === true);
      })
      .catch(() => {
        if (current) setAvailabilityFailed(true);
      });
    return () => {
      current = false;
    };
  }, [resetting, availabilityRevision]);

  async function submitRequest(event: FormEvent) {
    event.preventDefault();
    if (busy || available !== true) return;
    setBusy(true);
    setError("");
    setRequestMessage("");
    try {
      const result = await api<{ message: string }>(
        "/auth/password-reset/request",
        { email: email.trim() },
      );
      if (active.current) setRequestMessage(result.message);
    } catch (reason) {
      if (!active.current) return;
      setError(
        recoveryRequestError(
          reason instanceof ApiError ? reason.status : undefined,
        ),
      );
    } finally {
      if (active.current) setBusy(false);
    }
  }

  async function submitPassword(event: FormEvent) {
    event.preventDefault();
    if (busy || !link?.token) return;
    const validation = validateRecoveryPassword(password, confirmation);
    setError(validation || "");
    if (validation) return;
    setBusy(true);
    try {
      await api("/auth/password-reset/confirm", {
        token: link.token,
        password,
        password_confirm: confirmation,
      });
      if (!active.current) return;
      setPassword("");
      setConfirmation("");
      setChanged(true);
      onPasswordChanged();
    } catch (reason) {
      if (!active.current) return;
      if (
        reason instanceof ApiError &&
        [400, 404, 410].includes(reason.status)
      ) {
        setPassword("");
        setConfirmation("");
        setInvalidLink(true);
        setError(
          "Dieser Link ist ungültig, abgelaufen oder bereits verwendet. Fordere bitte einen neuen Link an.",
        );
      } else if (reason instanceof ApiError && reason.status === 422)
        setError(
          "Das Passwort konnte nicht übernommen werden. Nutze 12 bis 256 Zeichen und gib es in beiden Feldern gleich ein.",
        );
      else if (reason instanceof ApiError && reason.status === 429)
        setError(
          "Es gab gerade zu viele Versuche. Bitte warte einige Minuten und versuche es dann erneut.",
        );
      else
        setError(
          "Das Passwort konnte gerade nicht geändert werden. Prüfe deine Internetverbindung und versuche es noch einmal.",
        );
    } finally {
      if (active.current) setBusy(false);
    }
  }

  return (
    <AuthLayout sourceUrl={sourceUrl}>
      <span className="welcome-icon">
        <Icon name="lock" size={28} />
      </span>
      <span className="eyebrow">DEIN PERSÖNLICHER ZUGANG</span>
      <h2 ref={heading} tabIndex={-1} className="auth-heading">
        {changed
          ? "Dein Passwort ist neu."
          : resetting
            ? "Ein neues Passwort für dich."
            : "Wieder in deinen Raum."}
      </h2>
      {changed ? (
        <div className="alert success" role="status">
          Dein Passwort wurde geändert. Dein altes Passwort ist ungültig und
          bisherige Anmeldungen sind beendet. Melde dich jetzt mit deinem neuen
          Passwort an.
        </div>
      ) : (
        <>
          <p>
            {resetting
              ? "Wähle ein Passwort, das du dir gut merken kannst."
              : "Gib die E-Mail-Adresse deines Zugangs ein. Darüber kannst du einen Link für ein neues Passwort anfordern."}
          </p>
          {offline && (
            <div className="alert" role="status">
              Du bist offline. Für das Zurücksetzen brauchst du eine
              Internetverbindung.
            </div>
          )}
          {missingToken ? (
            <div className="auth-recovery-help">
              {!invalidLink && (
                <div className="alert" role="status">
                  Hier fehlt ein gültiger Link. Nach dem Öffnen entfernen wir
                  ihn zu deinem Schutz aus der Adresszeile. Wenn du die Seite
                  neu geladen hast, öffne den ursprünglichen Link aus deiner
                  E-Mail noch einmal oder fordere einen neuen an.
                </div>
              )}
              {error && (
                <div
                  ref={feedback}
                  className="alert error"
                  role="alert"
                  tabIndex={-1}
                >
                  {error}
                </div>
              )}
              <button
                className="button primary login-button"
                type="button"
                onClick={onRequestNew}
              >
                Neuen Link anfordern <Icon name="arrow" size={18} />
              </button>
            </div>
          ) : resetting ? (
            <form
              className="auth-recovery-form"
              onSubmit={submitPassword}
              aria-busy={busy}
            >
              <label htmlFor="reset-password">Neues Passwort</label>
              <input
                id="reset-password"
                name="new-password"
                type={showPassword ? "text" : "password"}
                autoComplete="new-password"
                required
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                aria-describedby="reset-password-help"
                disabled={busy}
              />
              <p id="reset-password-help" className="auth-field-help">
                12 bis 256 Zeichen. Zum Beispiel drei Wörter, die nur du
                auswählst. Einfügen und Passwortmanager sind erlaubt.
              </p>
              <label htmlFor="reset-password-confirm">
                Neues Passwort wiederholen
              </label>
              <input
                id="reset-password-confirm"
                name="new-password-confirm"
                type={showPassword ? "text" : "password"}
                autoComplete="new-password"
                required
                value={confirmation}
                onChange={(event) => setConfirmation(event.target.value)}
                disabled={busy}
              />
              <label className="auth-password-toggle">
                <input
                  type="checkbox"
                  checked={showPassword}
                  onChange={(event) => setShowPassword(event.target.checked)}
                />{" "}
                Passwörter anzeigen
              </label>
              {error && (
                <div
                  ref={feedback}
                  className="alert error"
                  role="alert"
                  tabIndex={-1}
                >
                  {error}
                </div>
              )}
              <button
                className="button primary login-button"
                disabled={busy || offline}
              >
                {busy
                  ? "Passwort wird gespeichert …"
                  : "Neues Passwort speichern"}
                <Icon name="arrow" size={18} />
              </button>
            </form>
          ) : (
            <>
              {available === null && !availabilityFailed && (
                <div role="status" className="auth-field-help">
                  Verfügbarkeit wird geprüft …
                </div>
              )}
              {availabilityFailed && (
                <div className="auth-recovery-help">
                  <div className="alert" role="status">
                    Die Verfügbarkeit konnte gerade nicht geprüft werden. Prüfe
                    deine Internetverbindung.
                  </div>
                  <button
                    className="button secondary"
                    type="button"
                    onClick={() =>
                      setAvailabilityRevision((value) => value + 1)
                    }
                  >
                    Erneut prüfen
                  </button>
                </div>
              )}
              {available === false && (
                <div className="alert" role="status">
                  {unavailableMessage}
                </div>
              )}
              {available === true && (
                <form
                  className="auth-recovery-form"
                  onSubmit={submitRequest}
                  aria-busy={busy}
                >
                  <label htmlFor="recovery-email">
                    E-Mail-Adresse deines Zugangs
                  </label>
                  <input
                    id="recovery-email"
                    name="email"
                    type="email"
                    autoComplete="username"
                    required
                    value={email}
                    onChange={(event) => {
                      setEmail(event.target.value);
                      setError("");
                      setRequestMessage("");
                    }}
                    placeholder="dein.name@beispiel.de"
                    disabled={busy}
                  />
                  {(error || requestMessage) && (
                    <div
                      ref={feedback}
                      className={`alert ${error ? "error" : "success"}`}
                      role={error ? "alert" : "status"}
                      tabIndex={-1}
                    >
                      {error || requestMessage}
                    </div>
                  )}
                  {requestMessage && (
                    <p className="auth-field-help">
                      Prüfe auch deinen Spam-Ordner. Nur die E-Mail selbst
                      bestätigt den Eingang des Links. Du kannst die Adresse
                      oben korrigieren und erneut anfragen.
                    </p>
                  )}
                  <button
                    className="button primary login-button"
                    disabled={busy || offline}
                  >
                    {busy ? "Anfrage wird verarbeitet …" : "Link anfordern"}
                    <Icon name="arrow" size={18} />
                  </button>
                </form>
              )}
            </>
          )}
        </>
      )}
      <button
        type="button"
        className={`button ${changed ? "primary login-button" : "text auth-back"}`}
        disabled={busy}
        onClick={onBack}
      >
        Zurück zur Anmeldung
      </button>
    </AuthLayout>
  );
}
