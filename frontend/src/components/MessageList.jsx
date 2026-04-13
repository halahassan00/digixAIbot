/**
 * src/components/MessageList.jsx
 *
 * Renders the conversation history.
 * Auto-scrolls to the latest message.
 * Shows a typing indicator while isLoading is true.
 *
 * Props:
 *   messages  : Array<{ role: "user"|"assistant", text: string, language: string }>
 *   isLoading : bool
 */

import { useEffect, useRef } from "react";

function TypingIndicator() {
  return (
    <div className="message message--assistant">
      <div className="message__bubble">
        <div className="typing-indicator">
          <span /><span /><span />
        </div>
      </div>
    </div>
  );
}

export default function MessageList({ messages, isLoading }) {
  const bottomRef = useRef(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isLoading]);

  return (
    <div className="message-list" role="log" aria-live="polite">
      {messages.map((msg, i) => (
        <div
          key={i}
          className={`message message--${msg.role}`}
          dir={msg.language === "ar" ? "rtl" : "ltr"}
        >
          <div className="message__bubble">{msg.text}</div>
        </div>
      ))}

      {isLoading && <TypingIndicator />}

      <div ref={bottomRef} />
    </div>
  );
}
