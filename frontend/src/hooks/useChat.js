/**
 * src/hooks/useChat.js
 *
 * Manages conversation state and calls the /chat endpoint.
 *
 * session_id is generated once per browser session (sessionStorage) so
 * the backend can maintain per-session conversation history.
 */

import { useCallback, useState } from "react";
import { v4 as uuidv4 } from "uuid";
import { sendMessage } from "../utils/api";

// Generate or reuse session ID for the browser tab lifetime
function getSessionId() {
  let id = sessionStorage.getItem("digix_session_id");
  if (!id) {
    id = uuidv4();
    sessionStorage.setItem("digix_session_id", id);
  }
  return id;
}

const SESSION_ID = getSessionId();

/**
 * @typedef {{ role: "user"|"assistant", text: string, language: string }} Message
 */

export function useChat(initialLanguage = "ar") {
  const [messages,    setMessages]    = useState([]);
  const [isLoading,   setIsLoading]   = useState(false);
  const [language,    setLanguage]    = useState(initialLanguage);
  const [collectLead, setCollectLead] = useState(false);

  const send = useCallback(async (text) => {
    if (!text.trim()) return;

    // Optimistically add the user message
    setMessages((prev) => [...prev, { role: "user", text, language }]);
    setIsLoading(true);
    setCollectLead(false);

    try {
      const result = await sendMessage(text, SESSION_ID, language);

      setMessages((prev) => [
        ...prev,
        { role: "assistant", text: result.response, language: result.language },
      ]);

      // Update language to whatever the bot detected (may differ from initial)
      setLanguage(result.language);
      setCollectLead(result.collect_lead);
    } catch {
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          text: language === "ar"
            ? "عذراً، حدث خطأ. يرجى المحاولة مرة أخرى."
            : "Sorry, something went wrong. Please try again.",
          language,
        },
      ]);
    } finally {
      setIsLoading(false);
    }
  }, [language]);

  return { messages, isLoading, language, collectLead, send };
}
