import type { ReactNode } from "react";
import { Brand, Icon, OrbitArt } from "./ui";
import { InfinityMark } from "./Dedication";

export function AuthLayout({
  children,
  sourceUrl,
}: {
  children: ReactNode;
  sourceUrl: string | null;
}) {
  return (
    <div className="login-page">
      <div className="login-story">
        <a
          className="brand-link"
          href="#home"
          aria-label="Sense & Stars – Anmeldung"
        >
          <Brand dark />
        </a>
        <div className="login-story-content">
          <span className="eyebrow">ANKOMMEN. VERBINDEN. ENTFALTEN.</span>
          <h1>
            Ein Raum.
            <br />
            Unendlich viel
            <br /> <em>Entwicklung.</em>
          </h1>
          <p>
            Für die Menschen, die du begleitest.
            <br />
            Und für deinen eigenen Weg.
          </p>
          <div className="login-dedication">
            <span>Für Marina</span>
            <InfinityMark />
          </div>
          <OrbitArt />
        </div>
        <div className="login-story-footer">
          <span className="mini-chakras" aria-hidden="true">
            {[
              "root",
              "sacral",
              "solar",
              "heart",
              "throat",
              "third-eye",
              "crown",
            ].map((tone) => (
              <i key={tone} style={{ background: `var(--chakra-${tone})` }} />
            ))}
          </span>
          <span>In deinem Rhythmus. Mit klarem Blick.</span>
        </div>
      </div>
      <main className="login-form-wrap">
        <div className="login-form">
          {children}
          <p className="login-security">
            <Icon name="lock" size={14} /> Dein Zugang ist persönlich und
            geschützt.
          </p>
          {sourceUrl && (
            <p className="login-security">
              <a
                className="text-link"
                href={sourceUrl}
                target="_blank"
                rel="noopener noreferrer"
              >
                Quellcode · AGPL
              </a>
            </p>
          )}
          <div className="login-disclaimer">
            Astrologie dient der spirituellen Reflexion. Sense &amp; Stars
            ersetzt keine medizinische oder psychotherapeutische Beratung.
          </div>
        </div>
      </main>
    </div>
  );
}
