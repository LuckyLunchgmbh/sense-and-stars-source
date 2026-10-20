import { useId, useState } from "react";
import type { Chart } from "./types";
import {
  BODY_MODEL_VERSION,
  bodyModel,
  PLANET_LABELS,
  type BodyCenterId,
} from "./bodyModel";
import { ContextHelp } from "./Help";

export function BodyChart({ chart }: { chart: Chart }) {
  const [selected, setSelected] = useState<BodyCenterId>("heart");
  const model = bodyModel(chart),
    center = model.centers.find((item) => item.id === selected)!;
  const links = model.links.filter(
    (link) => link.from === selected || link.to === selected,
  );
  const titleId = useId();
  return (
    <div className="body-chart">
      <div className="body-chart-intro">
        <div>
          <span className="eyebrow">{BODY_MODEL_VERSION}</span>
          <h3>Den Zusammenhang erkunden.</h3>
        </div>
        <ContextHelp topic="body" />
        <p>
          Dieselbe Sternenkarte, als menschliche Figur angeordnet. Die Zuordnung
          ist eine offengelegte Lernhilfe. Linien zeigen vorhandene
          Radix-Aspekte; ihre Richtung und Stärke sagen nichts über einen
          körperlichen Energiefluss aus.
        </p>
      </div>
      <div
        className="body-center-options"
        role="group"
        aria-label="Symbolisches Zentrum auswählen"
      >
        {model.centers.map((item) => (
          <button
            key={item.id}
            aria-pressed={selected === item.id}
            onClick={() => setSelected(item.id)}
            className={selected === item.id ? "selected" : ""}
            style={
              {
                "--node-color": `var(--chakra-${item.id})`,
              } as React.CSSProperties
            }
          >
            <i />
            {item.name}
          </button>
        ))}
      </div>
      <div className="body-chart-layout">
        <div className="body-figure-wrap">
          <svg
            viewBox="0 0 420 620"
            className="body-figure"
            role="img"
            aria-labelledby={titleId}
          >
            <title id={titleId}>
              Sieben symbolische Zentren. Wähle ein Zentrum, um seine
              berechneten Radix-Faktoren zu sehen.
            </title>
            <ellipse
              className="body-aura"
              cx="210"
              cy="300"
              rx="172"
              ry="280"
            />
            <path
              className="body-outline"
              d="M185 152 C166 132 170 91 188 78 C199 68 221 68 232 78 C250 91 254 132 235 152 L235 170 C246 180 270 185 282 204 C294 230 305 267 315 303 L330 353 C336 374 323 379 316 363 L293 316 L266 255 L257 316 C255 337 268 353 268 381 L253 559 C252 570 267 580 267 589 C265 598 238 597 235 587 L220 416 L210 390 L200 416 L185 587 C182 597 155 598 153 589 C153 580 168 570 167 559 L152 381 C152 353 165 337 163 316 L154 255 L127 316 L104 363 C97 379 84 374 90 353 L105 303 C115 267 126 230 138 204 C150 185 174 180 185 170 Z"
            />
            <path className="body-centerline" d="M210 57 V365" />
            {links
              .filter((link) => link.from !== link.to)
              .map((link, index) => {
                const from = model.centers.find(
                  (item) => item.id === link.from,
                )!;
                const to = model.centers.find((item) => item.id === link.to)!;
                const bend = (index % 2 ? -1 : 1) * (42 + (index % 4) * 16);
                return (
                  <path
                    key={link.id}
                    className="body-aspect-line"
                    d={`M210 ${from.y} Q${210 + bend} ${(from.y + to.y) / 2} 210 ${to.y}`}
                  >
                    <title>
                      {PLANET_LABELS[link.planet1]} –{" "}
                      {PLANET_LABELS[link.planet2]}: {link.aspect}, Orbis{" "}
                      {link.orb.toFixed(2)}°
                    </title>
                  </path>
                );
              })}
            {model.centers.map((item, index) => (
              <g
                key={item.id}
                className={
                  "body-node " + (selected === item.id ? "selected" : "")
                }
                aria-hidden="true"
                style={
                  {
                    "--node-color": `var(--chakra-${item.id})`,
                  } as React.CSSProperties
                }
              >
                <circle
                  className="body-node-halo"
                  cx="210"
                  cy={item.y}
                  r="24"
                />
                <circle
                  className="body-node-core"
                  cx="210"
                  cy={item.y}
                  r="13"
                />
                <path d={`M239 ${item.y} H${index % 2 ? 303 : 117}`} />
                <text
                  x={index % 2 ? 310 : 110}
                  y={item.y + 5}
                  textAnchor={index % 2 ? "start" : "end"}
                >
                  {item.name}
                </text>
              </g>
            ))}
            <text
              x="210"
              y="611"
              textAnchor="middle"
              className="body-figure-caption"
            >
              Symbolische Zuordnung · keine Messung
            </text>
          </svg>
        </div>
        <section className="body-focus" aria-live="polite" aria-atomic="true">
          <span
            className="body-center-label"
            style={
              {
                "--node-color": `var(--chakra-${center.id})`,
              } as React.CSSProperties
            }
          >
            <i />
            {center.name}
          </span>
          <h3>{center.theme}</h3>
          <p className="body-reflection">{center.question}</p>
          <h4>Zugeordnete Radix-Faktoren</h4>
          {center.factors.length ? (
            <ul className="body-factors">
              {center.factors.map((planet) => (
                <li key={planet.name}>
                  <strong>{PLANET_LABELS[planet.name] || planet.name}</strong>
                  <span>
                    {planet.sign} {planet.degree.toFixed(2)}° · Haus{" "}
                    {planet.house}
                    {planet.retrograde ? " · rückläufig" : ""}
                  </span>
                </li>
              ))}
            </ul>
          ) : (
            <p>
              Für diese Lernzuordnung ist im vorliegenden Radix kein Faktor
              vorhanden.
            </p>
          )}
          <h4>Verbindungen im berechneten Radix</h4>
          {links.length ? (
            <ul className="body-links">
              {links.map((link) => (
                <li key={link.id}>
                  <strong>
                    {PLANET_LABELS[link.planet1]} –{" "}
                    {PLANET_LABELS[link.planet2]}
                  </strong>
                  <span>
                    {link.aspect} · Orbis {link.orb.toFixed(2)}°
                    {link.from === link.to
                      ? " · innerhalb dieses Zentrums"
                      : ""}
                  </span>
                </li>
              ))}
            </ul>
          ) : (
            <p>
              Kein in den Berechnungsdaten enthaltener Aspekt für diese
              Faktoren. Das bedeutet keine Blockade.
            </p>
          )}
        </section>
      </div>
      <details className="body-method">
        <summary>Wie entsteht diese Darstellung?</summary>
        <p>
          Planetenpositionen, Zeichen, Häuser und Aspekte kommen unverändert aus
          der Radix-Berechnung. SoulFlow ordnet für diese Lernansicht Saturn und
          Pluto der Wurzel, den Mond dem Sakralzentrum, Sonne und Mars dem
          Solarplexus, Venus dem Herz, Merkur der Kehle, Uranus der Stirn sowie
          Jupiter und Neptun der Krone zu. Diese feste didaktische Konvention
          ist keine astronomische Berechnung von Chakren, keine individuelle
          Diagnose und keine Human-Design-Grafik.
        </p>
        <p>
          Ein Aspekt erscheint als Linie zwischen den zugeordneten Zentren. Die
          Kurve dient nur der Lesbarkeit. Es werden keine offenen oder
          geschlossenen Zentren, Tore, Kanäle, Stärken, Blockaden oder
          Eigenschaften der Person daraus berechnet.
        </p>
        {model.unassigned.length > 0 && (
          <p>
            Ohne Zuordnung in diesem Modell:{" "}
            {model.unassigned
              .map((planet) => PLANET_LABELS[planet.name] || planet.name)
              .join(", ")}
            . Sie bleiben in der Radix-Tabelle vollständig sichtbar.
          </p>
        )}
      </details>
    </div>
  );
}
