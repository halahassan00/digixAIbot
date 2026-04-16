/**
 * src/components/ChatWidget.jsx
 *
 * Floating chat widget with:
 *   - Animated robot launcher (pop-spin on load, spin on hover)
 *   - Suggested question chips (shown before first message)
 *   - Two voice modes: voice-to-text (mic → textarea) and voice-to-voice (auto TTS)
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

/* --------------------------------------------------------------------------
   Robot SVG icon (white, displayed inside the launcher button)
-------------------------------------------------------------------------- */
function RobotIcon() {
  return (
    <svg viewBox="0 0 32 32" fill="none" xmlns="http://www.w3.org/2000/svg">
      {/* Antenna */}
      <line x1="16" y1="2" x2="16" y2="7" stroke="white" strokeWidth="2" strokeLinecap="round"/>
      <circle cx="16" cy="2" r="1.5" fill="white"/>
      {/* Head */}
      <rect x="6" y="7" width="20" height="14" rx="4" fill="white" fillOpacity="0.95"/>
      {/* Eyes */}
      <circle cx="11.5" cy="13" r="2.5" fill="#6196ff"/>
      <circle cx="20.5" cy="13" r="2.5" fill="#b133ff"/>
      {/* Mouth */}
      <rect x="11" y="17" width="10" height="2" rx="1" fill="#6196ff" fillOpacity="0.7"/>
      {/* Body */}
      <rect x="9" y="22" width="14" height="8" rx="3" fill="white" fillOpacity="0.8"/>
      {/* Body detail */}
      <rect x="13" y="25" width="6" height="2" rx="1" fill="#b133ff" fillOpacity="0.6"/>
    </svg>
  );
}

/* --------------------------------------------------------------------------
   Suggested questions per language
-------------------------------------------------------------------------- */
const SUGGESTED_QUESTIONS = {
  ar: [
    "ما هي خدمات Digix AI؟",
    "كيف أتواصل معكم؟",
    "ما هي برامج التدريب المتاحة؟",
  ],
  en: [
    "What services does Digix AI offer?",
    "How can I contact you?",
    "What training programs are available?",
  ],
};

const GREETING = {
  ar: "مرحباً! كيف يمكنني مساعدتك اليوم؟",
  en: "Hello! How can I help you today?",
};

/* --------------------------------------------------------------------------
   ChatWidget
-------------------------------------------------------------------------- */
export default function ChatWidget({ defaultLanguage = "ar" }) {
  const [isOpen,       setIsOpen]       = useState(false);
  const [showLeadForm, setShowLeadForm] = useState(false);

  // Text state lifted here so voice-to-text can populate the textarea
  const [text, setText] = useState("");

  // Controls whether TTS plays after the next bot reply (voice-to-voice mode)
  const [ttsEnabled, setTtsEnabled] = useState(false);

  // Tracks which voice button is recording: "text" | "speech" | null
  const [voiceMode, setVoiceMode] = useState(null);

  // Intro animation on first paint
  const [showIntro, setShowIntro] = useState(true);
  useEffect(() => {
    const t = setTimeout(() => setShowIntro(false), 700);
    return () => clearTimeout(t);
  }, []);

  const panelRef = useRef(null);

  const { messages, isLoading, language, collectLead, send } = useChat(defaultLanguage);
  const { isRecording, isPlaying, startRecording, stopRecording, playResponse } = useVoice();

  // Show lead form when pipeline signals it
  useEffect(() => {
    if (collectLead) setShowLeadForm(true);
  }, [collectLead]);

  // Update panel direction when language changes
  useEffect(() => {
    applyDirection(panelRef.current, language);
  }, [language]);

  // TTS playback — only when ttsEnabled (voice-to-voice mode)
  const lastAssistant = [...messages].reverse().find((m) => m.role === "assistant");
  const lastAssistantRef = useRef(null);

  useEffect(() => {
    if (
      ttsEnabled &&
      lastAssistant &&
      lastAssistant !== lastAssistantRef.current &&
      !isLoading
    ) {
      lastAssistantRef.current = lastAssistant;
      playResponse(lastAssistant.text, lastAssistant.language)
        .catch(() => {})
        .finally(() => setTtsEnabled(false));
    }
  }, [lastAssistant, isLoading, ttsEnabled, playResponse]);

  /* -------------------------------------------------------------------------
     Handlers
  -------------------------------------------------------------------------- */

  const handleSend = async (msg) => {
    const trimmed = (msg ?? text).trim();
    if (!trimmed) return;
    setText("");
    await send(trimmed);
  };

  // Voice-to-text: stops recording → puts transcript in textarea, no auto-send
  const handleVoiceTextStart = () => {
    setVoiceMode("text");
    startRecording();
  };
  const handleVoiceTextStop = async () => {
    const result = await stopRecording();
    setVoiceMode(null);
    if (result?.text) setText(result.text);
  };

  // Voice-to-voice: stops recording → auto-sends + enables TTS for reply
  const handleVoiceSpeechStart = () => {
    setVoiceMode("speech");
    startRecording();
  };
  const handleVoiceSpeechStop = async () => {
    setTtsEnabled(true);
    const result = await stopRecording();
    setVoiceMode(null);
    if (result?.text) await send(result.text);
    else setTtsEnabled(false);
  };

  const handleLeadSubmit = async (lead) => {
    await submitLead(lead);
    setShowLeadForm(false);
  };

  /* -------------------------------------------------------------------------
     Display data
  -------------------------------------------------------------------------- */

  const displayMessages =
    messages.length === 0
      ? [{ role: "assistant", text: GREETING[defaultLanguage] || GREETING.ar, language: defaultLanguage }]
      : messages;

  const suggestedQuestions =
    messages.length === 0
      ? (SUGGESTED_QUESTIONS[language] || SUGGESTED_QUESTIONS.ar)
      : [];

  /* -------------------------------------------------------------------------
     Render
  -------------------------------------------------------------------------- */

  return (
    <>
      {/* Launcher bubble */}
      <button
        className={`chat-launcher${showIntro ? " chat-launcher--intro" : ""}`}
        onClick={() => setIsOpen((o) => !o)}
        aria-label={isOpen ? "Close chat" : "Open chat"}
      >
        {isOpen ? "✕" : <RobotIcon />}
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

          {/* Lead form */}
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
            text={text}
            onTextChange={setText}
            onSend={handleSend}
            isRecordingText={voiceMode === "text"}
            onVoiceTextStart={handleVoiceTextStart}
            onVoiceTextStop={handleVoiceTextStop}
            isRecordingSpeech={voiceMode === "speech"}
            onVoiceSpeechStart={handleVoiceSpeechStart}
            onVoiceSpeechStop={handleVoiceSpeechStop}
            suggestedQuestions={suggestedQuestions}
            onSuggestedQuestion={(q) => handleSend(q)}
          />
        </div>
      )}
    </>
  );
}
