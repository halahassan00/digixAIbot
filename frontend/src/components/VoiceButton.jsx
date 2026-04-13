/**
 * src/components/VoiceButton.jsx
 *
 * Mic button — starts/stops recording. Shows a pulse animation while recording.
 *
 * Props:
 *   isRecording : bool
 *   isDisabled  : bool
 *   onStart     : () => void
 *   onStop      : () => Promise<void>
 */

export default function VoiceButton({ isRecording, isDisabled, onStart, onStop }) {
  const handleClick = () => {
    if (isRecording) onStop();
    else onStart();
  };

  return (
    <button
      className={`input-bar__btn voice-btn ${isRecording ? "voice-btn--recording" : ""}`}
      onClick={handleClick}
      disabled={isDisabled}
      title={isRecording ? "إيقاف التسجيل" : "تسجيل صوتي"}
      aria-label={isRecording ? "Stop recording" : "Start voice input"}
    >
      {isRecording ? "⏹" : "🎙"}
    </button>
  );
}
