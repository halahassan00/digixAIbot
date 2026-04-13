/**
 * src/components/ChatWidget.jsx
 *
 * The main chat widget — a floating launcher bubble that opens a chat panel.
 *
 * Orchestrates:
 *   - useChat     → conversation state, /chat API calls
 *   - useVoice    → mic recording, /transcribe, /tts playback
 *   - MessageList → renders messages + typing indicator
 *   - InputBar    → text input + voice button
 *   - LeadForm    → shown when backend sets collect_lead=true
 */

import { useEffect, useRef, useState } from "react";
import "../styles/widget.css";
import { submitLead } from "../utils/api";
import { applyDirection } from "../utils/language";
import { useChat } from "../hooks/useChat";
import { useVoice } from "../hooks/useVoice";
import InputBar    from "./InputBar";
import LeadForm    from "./LeadForm";
import MessageList from "./MessageList";

const GREETING = {
  ar: "مرحباً! كيف يمكنني مساعدتك اليوم؟",
  en: "Hello! How can I help you today?",
};

export default function ChatWidget({ defaultLanguage = "ar" }) {
  const [isOpen,       setIsOpen]       = useState(false);
  const [showLeadForm, setShowLeadForm] = useState(false);

  const panelRef = useRef(null);

  const { messages, isLoading, language, collectLead, send } = useChat(defaultLanguage);
  const { isRecording, isPlaying, startRecording, stopRecording, playResponse } = useVoice();

  // Show lead form when the pipeline signals it
  useEffect(() => {
    if (collectLead) setShowLeadForm(true);
  }, [collectLead]);

  // Update panel direction when language changes
  useEffect(() => {
    applyDirection(panelRef.current, language);
  }, [language]);

  // -------------------------------------------------------------------------
  // Handlers
  // -------------------------------------------------------------------------

  const handleSend = async (text) => {
    await send(text);
    // Auto-play the latest assistant response via TTS
    // (messages state updates asynchronously — playback is triggered via
    //  the messages array in a separate effect to avoid stale closure issues)
  };

  // Play the latest assistant message whenever a new one arrives
  const lastAssistant = [...messages].reverse().find((m) => m.role === "assistant");
  const lastAssistantRef = useRef(null);

  useEffect(() => {
    if (
      lastAssistant &&
      lastAssistant !== lastAssistantRef.current &&
      !isLoading
    ) {
      lastAssistantRef.current = lastAssistant;
      // TTS is opt-in — only play if the voice pipeline is available.
      // Catch silently so a missing Azure key doesn't break the chat UI.
      playResponse(lastAssistant.text, lastAssistant.language).catch(() => {});
    }
  }, [lastAssistant, isLoading, playResponse]);

  const handleVoiceStop = async () => {
    const result = await stopRecording();
    if (result?.text) {
      await send(result.text);
    }
  };

  const handleLeadSubmit = async (lead) => {
    await submitLead(lead);
    setShowLeadForm(false);
  };

  // -------------------------------------------------------------------------
  // Greeting message (injected client-side, not from backend)
  // -------------------------------------------------------------------------

  const displayMessages =
    messages.length === 0
      ? [{ role: "assistant", text: GREETING[defaultLanguage] || GREETING.ar, language: defaultLanguage }]
      : messages;

  // -------------------------------------------------------------------------
  // Render
  // -------------------------------------------------------------------------

  return (
    <>
      {/* Launcher bubble */}
      <button
        className="chat-launcher"
        onClick={() => setIsOpen((o) => !o)}
        aria-label={isOpen ? "Close chat" : "Open chat"}
      >
        {isOpen ? "✕" : "💬"}
      </button>

      {/* Chat panel */}
      {isOpen && (
        <div className="chat-widget" ref={panelRef}>
          {/* Header */}
          <div className="chat-header">
            <div>
              <div className="chat-header__title">DIGIX AI</div>
              <div className="chat-header__subtitle">
                {language === "ar" ? "مساعدك الذكي" : "Your AI assistant"}
              </div>
            </div>
          </div>

          {/* Messages */}
          <MessageList messages={displayMessages} isLoading={isLoading} />

          {/* Lead form (shown above input bar when triggered) */}
          {showLeadForm && (
            <LeadForm
              language={language}
              onSubmit={handleLeadSubmit}
              onDismiss={() => setShowLeadForm(false)}
            />
          )}

          {/* Input */}
          <InputBar
            language={language}
            isLoading={isLoading || isPlaying}
            isRecording={isRecording}
            onSend={handleSend}
            onVoiceStart={startRecording}
            onVoiceStop={handleVoiceStop}
          />
        </div>
      )}
    </>
  );
}
