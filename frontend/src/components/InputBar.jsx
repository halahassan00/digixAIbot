/**
 * src/components/InputBar.jsx
 *
 * Layout (top to bottom):
 *   1. Suggested question chips (only before first user message)
 *   2. Input row: [mic-text] [textarea] [mic-speech] [send]
 *
 * Two voice buttons:
 *   - voice-to-text (mic icon): records → transcript fills textarea → user sends manually
 *   - voice-to-voice (waveform icon): records → auto-sends → TTS plays reply
 *
 * Props:
 *   language            : "ar" | "en"
 *   isLoading           : bool
 *   text                : string              — controlled from ChatWidget
 *   onTextChange        : (val: string) => void
 *   onSend              : (text?: string) => void
 *   isRecordingText     : bool
 *   onVoiceTextStart    : () => void
 *   onVoiceTextStop     : () => Promise<void>
 *   isRecordingSpeech   : bool
 *   onVoiceSpeechStart  : () => void
 *   onVoiceSpeechStop   : () => Promise<void>
 *   suggestedQuestions  : string[]
 *   onSuggestedQuestion : (q: string) => void
 */

import { useRef } from "react";

const PLACEHOLDERS = {
  ar: "اكتب رسالتك...",
  en: "Type your message...",
};

export default function InputBar({
  language,
  isLoading,
  text,
  onTextChange,
  onSend,
  isRecordingText,
  onVoiceTextStart,
  onVoiceTextStop,
  isRecordingSpeech,
  onVoiceSpeechStart,
  onVoiceSpeechStop,
  suggestedQuestions = [],
  onSuggestedQuestion,
}) {
  const textareaRef = useRef(null);
  const isRecording = isRecordingText || isRecordingSpeech;

  const submit = () => {
    if (!text.trim() || isLoading) return;
    onSend();
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
      {/* Suggested question chips */}
      {suggestedQuestions.length > 0 && (
        <div className="suggested-questions">
          {[...suggestedQuestions].sort((a, b) => b.length - a.length).map((q) => (
            <button
              key={q}
              className="suggested-q"
              onClick={() => onSuggestedQuestion(q)}
              disabled={isLoading}
            >
              {q}
            </button>
          ))}
        </div>
      )}

      {/* Input row */}
      <div className="input-bar__row">
        {/* Voice-to-text button (mic SVG icon) */}
        <button
          className={`input-bar__btn voice-btn--text${isRecordingText ? " recording" : ""}`}
          onClick={isRecordingText ? onVoiceTextStop : onVoiceTextStart}
          disabled={isLoading || isRecordingSpeech}
          title={language === "ar" ? "تحويل الصوت إلى نص" : "Voice to text"}
          aria-label={isRecordingText ? "Stop voice-to-text recording" : "Start voice-to-text"}
        >
          {isRecordingText ? (
            /* Stop square */
            <svg width="14" height="14" viewBox="0 0 14 14" fill="currentColor">
              <rect x="1" y="1" width="12" height="12" rx="2"/>
            </svg>
          ) : (
            /* Microphone */
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <rect x="9" y="2" width="6" height="11" rx="3"/>
              <path d="M5 10a7 7 0 0 0 14 0"/>
              <line x1="12" y1="17" x2="12" y2="21"/>
              <line x1="9" y1="21" x2="15" y2="21"/>
            </svg>
          )}
        </button>

        {/* Text input */}
        <textarea
          ref={textareaRef}
          className="input-bar__field"
          rows={1}
          placeholder={PLACEHOLDERS[language] || PLACEHOLDERS.ar}
          value={text}
          onChange={(e) => onTextChange(e.target.value)}
          onKeyDown={handleKeyDown}
          disabled={isLoading || isRecording}
          dir={language === "ar" ? "rtl" : "ltr"}
        />

        {/* Voice-to-voice button (waveform/speaker icon) */}
        <button
          className={`input-bar__btn voice-btn--speech${isRecordingSpeech ? " recording" : ""}`}
          onClick={isRecordingSpeech ? onVoiceSpeechStop : onVoiceSpeechStart}
          disabled={isLoading || isRecordingText}
          title={language === "ar" ? "محادثة صوتية" : "Voice conversation"}
          aria-label={isRecordingSpeech ? "Stop voice conversation" : "Start voice conversation"}
        >
          {isRecordingSpeech ? "⏹" : "🔊"}
        </button>

        {/* Send button */}
        <button
          className="input-bar__btn input-bar__btn--send"
          onClick={submit}
          disabled={!text.trim() || isLoading}
          aria-label="Send"
        >
          {language === "ar" ? "←" : "→"}
        </button>
      </div>
    </div>
  );
}
