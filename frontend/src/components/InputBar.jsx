/**
 * src/components/InputBar.jsx
 *
 * Text input + send button + voice button.
 * Enter sends the message; Shift+Enter adds a newline.
 *
 * Props:
 *   language      : "ar" | "en"
 *   isLoading     : bool  — disables input while waiting for response
 *   isRecording   : bool
 *   onSend        : (text: string) => void
 *   onVoiceStart  : () => void
 *   onVoiceStop   : () => Promise<void>
 */

import { useRef, useState } from "react";
import VoiceButton from "./VoiceButton";

const PLACEHOLDERS = {
  ar: "اكتب رسالتك...",
  en: "Type your message...",
};

export default function InputBar({
  language,
  isLoading,
  isRecording,
  onSend,
  onVoiceStart,
  onVoiceStop,
}) {
  const [text, setText] = useState("");
  const textareaRef = useRef(null);

  const submit = () => {
    const trimmed = text.trim();
    if (!trimmed || isLoading) return;
    onSend(trimmed);
    setText("");
    textareaRef.current?.focus();
  };

  const handleKeyDown = (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      submit();
    }
  };

  return (
    <div className="input-bar">
      <VoiceButton
        isRecording={isRecording}
        isDisabled={isLoading}
        onStart={onVoiceStart}
        onStop={onVoiceStop}
      />

      <textarea
        ref={textareaRef}
        className="input-bar__field"
        rows={1}
        placeholder={PLACEHOLDERS[language] || PLACEHOLDERS.ar}
        value={text}
        onChange={(e) => setText(e.target.value)}
        onKeyDown={handleKeyDown}
        disabled={isLoading || isRecording}
        dir={language === "ar" ? "rtl" : "ltr"}
      />

      <button
        className="input-bar__btn input-bar__btn--send"
        onClick={submit}
        disabled={!text.trim() || isLoading}
        aria-label="Send"
      >
        {language === "ar" ? "←" : "→"}
      </button>
    </div>
  );
}
