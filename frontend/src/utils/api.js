/**
 * src/utils/api.js
 *
 * All fetch calls to the backend in one place.
 * Nothing else in the frontend calls fetch directly.
 *
 * Base URL comes from REACT_APP_BACKEND_URL env var.
 * In development, package.json "proxy" forwards /chat etc. to localhost:8000
 * so you can leave REACT_APP_BACKEND_URL unset during local dev.
 */

const BASE_URL = process.env.REACT_APP_BACKEND_URL || "";

// ---------------------------------------------------------------------------
// POST /chat
// ---------------------------------------------------------------------------

/**
 * Send a text message and get a response.
 *
 * @param {string} message
 * @param {string} sessionId
 * @param {string} language  "ar" | "en"
 * @returns {Promise<{ response: string, language: string, collect_lead: boolean }>}
 */
export async function sendMessage(message, sessionId, language) {
  const res = await fetch(`${BASE_URL}/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message, session_id: sessionId, language }),
  });
  if (!res.ok) throw new Error(`/chat failed: ${res.status}`);
  return res.json();
}

// ---------------------------------------------------------------------------
// POST /transcribe
// ---------------------------------------------------------------------------

/**
 * Send an audio blob to Whisper and get back the transcript + detected language.
 *
 * @param {Blob} audioBlob
 * @returns {Promise<{ text: string, language: string }>}
 */
export async function transcribeAudio(audioBlob) {
  const form = new FormData();
  form.append("file", audioBlob, "recording.webm");

  const res = await fetch(`${BASE_URL}/transcribe`, {
    method: "POST",
    body: form,
  });
  if (!res.ok) throw new Error(`/transcribe failed: ${res.status}`);
  return res.json();
}

// ---------------------------------------------------------------------------
// POST /tts
// ---------------------------------------------------------------------------

/**
 * Convert text to speech and return an audio Blob (mp3).
 *
 * @param {string} text
 * @param {string} language  "ar" | "en"
 * @returns {Promise<Blob>}
 */
export async function synthesizeSpeech(text, language) {
  const res = await fetch(`${BASE_URL}/tts`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text, language }),
  });
  if (!res.ok) throw new Error(`/tts failed: ${res.status}`);
  return res.blob();
}

// ---------------------------------------------------------------------------
// POST /leads
// ---------------------------------------------------------------------------

/**
 * Submit a lead to the backend.
 *
 * @param {{ name: string, email: string, org: string, interest: string, language: string }} lead
 * @returns {Promise<{ success: boolean }>}
 */
export async function submitLead(lead) {
  const res = await fetch(`${BASE_URL}/leads`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(lead),
  });
  if (!res.ok) throw new Error(`/leads failed: ${res.status}`);
  return res.json();
}
