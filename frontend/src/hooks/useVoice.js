/**
 * src/hooks/useVoice.js
 *
 * Handles microphone recording and TTS audio playback.
 *
 * Recording flow:
 *   startRecording() → MediaRecorder captures mic → stopRecording()
 *   → audio Blob → POST /transcribe → transcript text returned to caller
 *
 * Playback flow:
 *   playResponse(text, language) → POST /tts → mp3 Blob → Audio element plays it
 */

import { useCallback, useRef, useState } from "react";
import { synthesizeSpeech, transcribeAudio } from "../utils/api";

export function useVoice() {
  const [isRecording, setIsRecording] = useState(false);
  const [isPlaying,   setIsPlaying]   = useState(false);
  const [error,       setError]       = useState(null);

  const recorderRef  = useRef(null);
  const chunksRef    = useRef([]);
  const audioRef     = useRef(null);   // current Audio element for TTS playback

  // ---------------------------------------------------------------------------
  // Recording
  // ---------------------------------------------------------------------------

  const startRecording = useCallback(async () => {
    setError(null);
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const recorder = new MediaRecorder(stream, { mimeType: "audio/webm" });
      chunksRef.current = [];

      recorder.ondataavailable = (e) => {
        if (e.data.size > 0) chunksRef.current.push(e.data);
      };

      recorderRef.current = recorder;
      recorder.start();
      setIsRecording(true);
    } catch (err) {
      setError("Microphone access denied.");
    }
  }, []);

  /**
   * Stop recording and transcribe.
   * @returns {Promise<{ text: string, language: string } | null>}
   */
  const stopRecording = useCallback(() => {
    return new Promise((resolve) => {
      const recorder = recorderRef.current;
      if (!recorder || recorder.state === "inactive") {
        resolve(null);
        return;
      }

      recorder.onstop = async () => {
        // Stop all mic tracks so the browser stops showing the recording indicator
        recorder.stream.getTracks().forEach((t) => t.stop());

        const blob = new Blob(chunksRef.current, { type: "audio/webm" });
        chunksRef.current = [];
        setIsRecording(false);

        try {
          const result = await transcribeAudio(blob);
          resolve(result);
        } catch {
          setError("Transcription failed. Please try again.");
          resolve(null);
        }
      };

      recorder.stop();
    });
  }, []);

  // ---------------------------------------------------------------------------
  // TTS Playback
  // ---------------------------------------------------------------------------

  const playResponse = useCallback(async (text, language) => {
    // Stop any currently playing audio before starting new playback
    if (audioRef.current) {
      audioRef.current.pause();
      audioRef.current = null;
    }

    setIsPlaying(true);
    try {
      const blob = await synthesizeSpeech(text, language);
      const url  = URL.createObjectURL(blob);
      const audio = new Audio(url);
      audioRef.current = audio;

      audio.onended = () => {
        URL.revokeObjectURL(url);
        setIsPlaying(false);
      };
      audio.onerror = () => {
        setIsPlaying(false);
      };

      await audio.play();
    } catch {
      setIsPlaying(false);
    }
  }, []);

  return { isRecording, isPlaying, error, startRecording, stopRecording, playResponse };
}
