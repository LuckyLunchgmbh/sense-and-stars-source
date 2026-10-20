import {
  useEffect,
  useId,
  useRef,
  type ReactNode,
  type CSSProperties,
} from "react";
export type IconName =
  | "help"
  | "spark"
  | "home"
  | "calendar"
  | "users"
  | "orbit"
  | "book"
  | "settings"
  | "logout"
  | "arrow"
  | "plus"
  | "search"
  | "close"
  | "chevron"
  | "check"
  | "lock"
  | "leaf"
  | "heart"
  | "clock"
  | "note"
  | "audio"
  | "task"
  | "download"
  | "shield"
  | "sun"
  | "menu"
  | "eye"
  | "play"
  | "mail"
  | "chart"
  | "refresh";
const paths: Record<IconName, ReactNode> = {
  help: (
    <>
      <circle cx="12" cy="12" r="9" />
      <path d="M9.5 8.5a2.5 2.5 0 0 1 5 0c0 2-2.5 2-2.5 4M12 16h.01" />
    </>
  ),
  spark: (
    <>
      <path d="m12 3 2.4 6.6L21 12l-6.6 2.4L12 21l-2.4-6.6L3 12l6.6-2.4Z" />
      <path d="m20 2 .5 1.5L22 4l-1.5.5L20 6l-.5-1.5L18 4l1.5-.5Z" />
    </>
  ),
  home: (
    <>
      <path d="m3 10 9-7 9 7v10a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1Z" />
      <path d="M9 21v-8h6v8" />
    </>
  ),
  calendar: (
    <>
      <rect x="3" y="5" width="18" height="16" rx="3" />
      <path d="M16 3v4M8 3v4M3 11h18M8 15h2M14 15h2" />
    </>
  ),
  users: (
    <>
      <path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2M22 21v-2a4 4 0 0 0-3-3.87" />
      <circle cx="9" cy="7" r="4" />
      <path d="M16 3.13a4 4 0 0 1 0 7.75" />
    </>
  ),
  orbit: (
    <>
      <circle cx="12" cy="12" r="3" />
      <ellipse cx="12" cy="12" rx="10" ry="5" transform="rotate(-35 12 12)" />
      <ellipse cx="12" cy="12" rx="10" ry="5" transform="rotate(35 12 12)" />
    </>
  ),
  book: (
    <>
      <path d="M12 5c-4-3-9-1-9-1v16s5-2 9 1c4-3 9-1 9-1V4s-5-2-9 1ZM12 5v16" />
    </>
  ),
  settings: (
    <>
      <path d="m9 3-1 3-3 1-2 3 2 2-1 3 3 2 1 3h4l1-3 3-1 2-3-2-2 1-3-3-2-1-3Z" />
      <circle cx="10.5" cy="11.5" r="3" />
    </>
  ),
  logout: (
    <>
      <path d="M9 5H5v14h4M12 12h9m-4-4 4 4-4 4" />
    </>
  ),
  arrow: <path d="M4 12h16m-6-6 6 6-6 6" />,
  plus: <path d="M12 5v14M5 12h14" />,
  search: (
    <>
      <circle cx="10.5" cy="10.5" r="7.5" />
      <path d="m16 16 5 5" />
    </>
  ),
  close: <path d="m6 6 12 12M18 6 6 18" />,
  chevron: <path d="m9 5 7 7-7 7" />,
  check: <path d="m5 12 4 4L19 6" />,
  lock: (
    <>
      <rect x="5" y="10" width="14" height="11" rx="2" />
      <path d="M8 10V7a4 4 0 0 1 8 0v3M12 14v3" />
    </>
  ),
  leaf: (
    <>
      <path d="M20 3C8 2 1 8 4 16c7 6 17-1 16-13ZM5 18l10-10" />
    </>
  ),
  heart: (
    <path d="M20.8 4.6a5.5 5.5 0 0 0-7.8 0l-1 1-1-1a5.5 5.5 0 0 0-7.8 7.8L12 21l8.8-8.6a5.5 5.5 0 0 0 0-7.8Z" />
  ),
  clock: (
    <>
      <circle cx="12" cy="12" r="9" />
      <path d="M12 7v5l3 2" />
    </>
  ),
  note: (
    <>
      <rect x="4" y="3" width="16" height="18" rx="2" />
      <path d="M8 8h8M8 12h8M8 16h5" />
    </>
  ),
  audio: (
    <>
      <path d="M9 18V5l11-2v13M9 9l11-2" />
      <ellipse cx="6" cy="18" rx="3" ry="2" />
      <ellipse cx="17" cy="16" rx="3" ry="2" />
    </>
  ),
  task: (
    <>
      <rect x="4" y="4" width="16" height="17" rx="2" />
      <path d="m8 12 3 3 5-6M9 3h6" />
    </>
  ),
  download: (
    <>
      <path d="M12 3v12m-5-5 5 5 5-5M4 16v5h16v-5" />
    </>
  ),
  shield: (
    <>
      <path d="m12 2 9 4v6c0 5-9 10-9 10S3 17 3 12V6Z" />
      <path d="m8 12 3 3 5-6" />
    </>
  ),
  sun: (
    <>
      <circle cx="12" cy="12" r="4" />
      <path d="M12 2v2m0 16v2M2 12h2m16 0h2M5 5l1.5 1.5m11 11L19 19M5 19l1.5-1.5m11-11L19 5" />
    </>
  ),
  menu: <path d="M4 6h16M4 12h16M4 18h16" />,
  eye: (
    <>
      <path d="M2 12s4-7 10-7 10 7 10 7-4 7-10 7S2 12 2 12Z" />
      <circle cx="12" cy="12" r="3" />
    </>
  ),
  play: <path d="m8 4 12 8-12 8Z" />,
  mail: (
    <>
      <rect x="3" y="5" width="18" height="14" rx="2" />
      <path d="m3 6 9 7 9-7" />
    </>
  ),
  chart: (
    <>
      <path d="M4 3v17h17M8 15v-4m5 4V7m5 8v-6" />
    </>
  ),
  refresh: (
    <>
      <path d="M21 4v6h-6M3 20v-6h6" />
      <path d="M5 7a8 8 0 0 1 13-2l3 5M3 14l3 5a8 8 0 0 0 13-2" />
    </>
  ),
};
export function Icon({
  name,
  size = 20,
  className = "",
}: {
  name: IconName;
  size?: number;
  className?: string;
}) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.6"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      className={className}
    >
      {paths[name]}
    </svg>
  );
}
export function Modal({
  title,
  description,
  children,
  onClose,
  wide = false,
}: {
  title: string;
  description?: string;
  children: ReactNode;
  onClose: () => void;
  wide?: boolean;
}) {
  const ref = useRef<HTMLDialogElement>(null);
  const id = useId();
  useEffect(() => {
    const node = ref.current;
    const previous = document.activeElement as HTMLElement | null;
    let suspended = !navigator.onLine;
    const suspend = () => {
      suspended = Boolean(node?.open);
      node?.close();
    };
    const resume = () => {
      if (suspended && node?.isConnected && !node.open) node.showModal();
      suspended = false;
    };
    if (!suspended) node?.showModal();
    window.addEventListener("offline", suspend);
    window.addEventListener("online", resume);
    return () => {
      window.removeEventListener("offline", suspend);
      window.removeEventListener("online", resume);
      node?.close();
      previous?.focus();
    };
  }, []);
  return (
    <dialog
      ref={ref}
      className={"modal " + (wide ? "modal-wide" : "")}
      aria-labelledby={id}
      onCancel={(event) => {
        event.preventDefault();
        onClose();
      }}
      onClick={(event) => {
        if (event.target === event.currentTarget) {
          const r = event.currentTarget.getBoundingClientRect();
          if (
            event.clientX < r.left ||
            event.clientX > r.right ||
            event.clientY < r.top ||
            event.clientY > r.bottom
          )
            onClose();
        }
      }}
    >
      <div className="modal-top">
        <div>
          <span className="eyebrow">SOULFLOW</span>
          <h2 id={id}>{title}</h2>
          {description && <p>{description}</p>}
        </div>
        <button
          className="icon-button"
          onClick={onClose}
          aria-label="Dialog schließen"
        >
          <Icon name="close" />
        </button>
      </div>
      {children}
    </dialog>
  );
}
export function ErrorBox({ error }: { error: string | unknown }) {
  if (!error) return null;
  return (
    <div className="alert error" role="alert">
      <Icon name="shield" />
      <span>{error instanceof Error ? error.message : String(error)}</span>
    </div>
  );
}
export function Empty({
  icon = "leaf",
  title,
  children,
  action,
}: {
  icon?: IconName;
  title: string;
  children?: ReactNode;
  action?: ReactNode;
}) {
  return (
    <div className="empty-state">
      <span className="empty-icon">
        <Icon name={icon} size={30} />
      </span>
      <h3>{title}</h3>
      {children && <p>{children}</p>}
      {action}
    </div>
  );
}
export function Loading() {
  return (
    <div className="loading" role="status">
      <span className="spinner" />
      <span>Dein Raum wird geöffnet …</span>
    </div>
  );
}
export function Badge({
  children,
  tone = "neutral",
}: {
  children: ReactNode;
  tone?: string;
}) {
  return <span className={"badge " + tone}>{children}</span>;
}
export function Avatar({
  name,
  size = "normal",
}: {
  name: string;
  size?: "normal" | "large" | "small";
}) {
  return (
    <span className={"avatar " + size} aria-hidden="true">
      {name
        .split(" ")
        .map((p) => p[0])
        .slice(0, 2)
        .join("")}
    </span>
  );
}
export function SectionTitle({
  eyebrow,
  title,
  children,
}: {
  eyebrow?: string;
  title: string;
  children?: ReactNode;
}) {
  return (
    <div className="section-heading">
      <div>
        {eyebrow && <span className="eyebrow">{eyebrow}</span>}
        <h2>{title}</h2>
      </div>
      {children}
    </div>
  );
}
export function ChakraMark({ className = "" }: { className?: string }) {
  return (
    <svg
      className={className}
      viewBox="0 0 40 40"
      fill="none"
      aria-hidden="true"
    >
      <ellipse
        cx="20"
        cy="20"
        rx="8"
        ry="16"
        transform="rotate(40 20 20)"
        stroke="currentColor"
      />
      <ellipse
        cx="20"
        cy="20"
        rx="8"
        ry="16"
        transform="rotate(-40 20 20)"
        stroke="currentColor"
      />
      <path
        d="m20 11 2.5 6.5L29 20l-6.5 2.5L20 29l-2.5-6.5L11 20l6.5-2.5Z"
        fill="currentColor"
      />
    </svg>
  );
}
export function OrbitArt() {
  return (
    <svg
      className="orbit-art"
      viewBox="0 0 380 300"
      fill="none"
      aria-hidden="true"
    >
      <circle cx="218" cy="153" r="112" stroke="currentColor" opacity=".18" />
      <circle cx="218" cy="153" r="83" stroke="currentColor" opacity=".24" />
      <ellipse
        cx="218"
        cy="153"
        rx="147"
        ry="56"
        transform="rotate(-31 218 153)"
        stroke="currentColor"
        opacity=".5"
      />
      <ellipse
        cx="218"
        cy="153"
        rx="61"
        ry="126"
        transform="rotate(-31 218 153)"
        stroke="currentColor"
        opacity=".38"
      />
      <path
        d="m218 119 9.5 24.5L252 153l-24.5 9.5L218 187l-9.5-24.5L184 153l24.5-9.5Z"
        fill="currentColor"
        opacity=".75"
      />
      <circle cx="318" cy="89" r="7" fill="currentColor" />
      <circle cx="122" cy="245" r="4" fill="currentColor" opacity=".5" />
      <path
        d="M52 89h14m-7-7v14M322 227h12m-6-6v12"
        stroke="currentColor"
        opacity=".6"
      />
    </svg>
  );
}
export const toneStyle = (tone: string) =>
  ({ "--tone": `var(--chakra-${tone})` }) as CSSProperties;
