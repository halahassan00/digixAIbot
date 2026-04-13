/**
 * src/index.js
 *
 * Embeddable entry point.
 *
 * Standard usage (React app):
 *   Renders <App /> into #root — used during local development.
 *
 * Embeddable usage (digix-ai.com):
 *   When window.DIGIX_CHAT_EMBED is true, the widget mounts into a
 *   dedicated <div id="digix-chat-root"> injected by the embed script.
 *   This lets DIGIX AI add the chatbot to their site with one <script> tag
 *   without touching their existing React tree (if any).
 *
 *   Embed snippet for digix-ai.com:
 *     <div id="digix-chat-root"></div>
 *     <script>window.DIGIX_CHAT_EMBED = true;</script>
 *     <script src="https://<backend>/static/main.js"></script>
 */

import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App";

const mountId = window.DIGIX_CHAT_EMBED ? "digix-chat-root" : "root";
const mountEl = document.getElementById(mountId);

if (mountEl) {
  ReactDOM.createRoot(mountEl).render(
    <React.StrictMode>
      <App />
    </React.StrictMode>
  );
}
