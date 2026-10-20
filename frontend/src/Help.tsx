import { useState } from "react";
import { go } from "./hooks";
import { Icon, Modal } from "./ui";
const helpTopics = {
  practice: {
    title: "In Ruhe ausprobieren",
    text: "Im Übungsmodus arbeitest du mit eigenen fiktiven Testpersonen. Du kannst Beispiele laden, eine eigene Testperson anlegen und dieselben Abläufe wie in der Praxis üben. Die Auswahl, Termine und Übersicht sind von den Praxisdaten getrennt. Gelöschte Testpersonen liegen im Testarchiv und können wiederhergestellt werden.",
    next: "Wähle oben Üben und öffne die Testpersonen. Drei Beispiele bringen bereits eine berechnete Sternenkarte mit.",
  },
  clients: {
    title: "Menschen auswählen und begleiten",
    text: "Öffne ein Profil für Geburtsangaben, Sternenkarte und Begleitimpulse. In der Sternenkarte kannst du die Person auch direkt über die Auswahl wechseln. Ohne genaue Geburtszeit und eindeutig gewählten Ort wird kein Radix geraten.",
    next: "Nur im Übungsmodus lassen sich Testpersonen löschen. Das betrifft ausschließlich deine eigenen Testdaten.",
  },
  chart: {
    title: "Ein Radix öffnen",
    text: "Wähle eine Person mit Geburtsdatum und Geburtszeit. Suche den Geburtsort ausdrücklich, bestätige den passenden Treffer und berechne die Karte. Radix und Körperansicht verwenden dieselben gespeicherten Berechnungsdaten.",
    next: "Du findest Zeichen, Häuser und Aspekte in den Tabellen. Die Herkunft und Ortszeit stehen direkt unter der Darstellung.",
  },
  body: {
    title: "Die Körperansicht lesen",
    text: "Die menschliche Figur ist das SoulFlow-Symbolmodell. Wähle eines der sieben Zentren. Daneben siehst du die zugeordneten Planeten mit Zeichen, Grad, Haus und ihren vorhandenen Radix-Aspekten. Unter der Darstellung steht die vollständige feste Zuordnungsregel.",
    next: "Die Linien visualisieren astrologische Beziehungen. Sie messen keinen Energiefluss, keine Blockaden und keine körperlichen Befunde. Für die originalen Positionen wechselst du jederzeit zu Radix.",
  },
  calendar: {
    title: "Eine Sitzung üben oder planen",
    text: "Wähle eine Person und einen zukünftigen Zeitpunkt. Alle Termine werden in Europa/Berlin angezeigt. Vor dem Sitzungsstart bestätigst du deinen persönlichen Vorbereitungsrahmen. Anschließend kannst du die Sitzung abschließen oder einen geplanten Termin absagen.",
    next: "Im Übungsmodus erscheinen ausschließlich Termine deiner Testpersonen. Testtermine gehen nicht in die Praxisübersicht ein.",
  },
  learning: {
    title: "Wie war das noch einmal?",
    text: "Alle veröffentlichten Kapitel sind frei zugänglich. Suche nach einem Begriff oder nutze die Themenfilter. Merke Kapitel für später, pinne wichtige Inhalte an deine Pinnwand oder halte eine eigene Notiz fest. Ein Quiz ist freiwillig.",
    next: "Dein Notizbuch gehört zu deinem Konto. Speichere Änderungen vor dem Wechsel und lade bei Bedarf eine Markdown-Kopie herunter.",
  },
} as const;
export type HelpTopic = keyof typeof helpTopics;
export function ContextHelp({ topic }: { topic: HelpTopic }) {
  const [open, setOpen] = useState(false),
    help = helpTopics[topic];
  return (
    <>
      <button
        className="context-help"
        type="button"
        aria-label={`Hilfe: ${help.title}`}
        title={help.title}
        onClick={() => setOpen(true)}
      >
        <Icon name="help" size={18} />
      </button>
      {open && (
        <Modal title={help.title} onClose={() => setOpen(false)}>
          <div className="help-modal-copy">
            <p>{help.text}</p>
            <p>{help.next}</p>
          </div>
          <div className="form-actions">
            <button
              className="button text"
              onClick={() => {
                setOpen(false);
                go("help");
              }}
            >
              Alle Anleitungen
            </button>
            <button className="button primary" onClick={() => setOpen(false)}>
              Verstanden
            </button>
          </div>
        </Modal>
      )}
    </>
  );
}
export function HelpPage() {
  return (
    <>
      <div className="page-heading">
        <div>
          <span className="eyebrow">WIE WAR DAS NOCH EINMAL?</span>
          <h1>Dein Begleiter für zwischendurch.</h1>
          <p>Kurze Anleitungen, die du jederzeit wieder öffnen kannst.</p>
        </div>
        <Icon name="help" size={36} />
      </div>
      <section className="help-start glass-card">
        <div>
          <span className="eyebrow">EIN GUTER ERSTER DURCHLAUF</span>
          <h2>Mit einer fiktiven Person beginnen.</h2>
          <p>
            Wechsle zu Üben, lade die drei Beispiele und öffne eine
            Sternenkarte. Probiere beide Darstellungen aus. Plane dann einen
            Testtermin und notiere deine Beobachtungen.
          </p>
        </div>
        <button
          className="button primary"
          onClick={() => {
            window.location.hash = "practice/clients";
          }}
        >
          Übungsraum öffnen <Icon name="arrow" size={17} />
        </button>
      </section>
      <div className="help-grid">
        {Object.entries(helpTopics).map(([id, item], index) => (
          <article
            className="glass-card help-article"
            key={id}
            id={`help-${id}`}
          >
            <span className="help-number">0{index + 1}</span>
            <h2>{item.title}</h2>
            <p>{item.text}</p>
            <p className="help-next">{item.next}</p>
            <button
              className="text-link"
              onClick={() =>
                go(
                  id === "practice" || id === "clients"
                    ? "clients"
                    : id === "chart" || id === "body"
                      ? "astro"
                      : id === "calendar"
                        ? "calendar"
                        : "learning",
                )
              }
            >
              Bereich öffnen <Icon name="arrow" size={15} />
            </button>
          </article>
        ))}
      </div>
      <section className="glass-card help-boundary">
        <Icon name="shield" size={22} />
        <p>
          Astrologie und die Körperansicht dienen der spirituellen Reflexion.
          Eine Vermutung über einen Menschen wird erst durch dessen freiwillige
          Rückmeldung überprüfbar. SoulFlow ersetzt keine medizinische oder
          psychotherapeutische Beratung.
        </p>
      </section>
    </>
  );
}
