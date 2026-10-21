import React from "react";
import { createRoot } from "react-dom/client";
import App from "./App";
import "./styles.css";
import { captureRecoveryLink } from "./recoveryLink";

const initialRecoveryLink = captureRecoveryLink(
  window.location,
  window.history,
);
createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App initialRecoveryLink={initialRecoveryLink} />
  </React.StrictMode>,
);
if ("serviceWorker" in navigator && import.meta.env.PROD)
  window.addEventListener("load", () => {
    navigator.serviceWorker.register("/sw.js").catch(() => {});
  });
