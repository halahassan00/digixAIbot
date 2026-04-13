/**
 * src/components/LeadForm.jsx
 *
 * Inline lead collection form, shown when the chat backend sets collect_lead=true.
 * Collects: name, email, org (optional), interest.
 *
 * Props:
 *   language   : "ar" | "en"
 *   onSubmit   : (lead: object) => Promise<void>
 *   onDismiss  : () => void
 */

import { useState } from "react";

const LABELS = {
  ar: {
    title:    "تواصل مع فريقنا",
    name:     "الاسم",
    email:    "البريد الإلكتروني",
    org:      "المؤسسة (اختياري)",
    interest: "موضع الاهتمام",
    submit:   "إرسال",
    dismiss:  "لاحقاً",
  },
  en: {
    title:    "Get in touch",
    name:     "Name",
    email:    "Email",
    org:      "Organisation (optional)",
    interest: "Topic of interest",
    submit:   "Submit",
    dismiss:  "Maybe later",
  },
};

export default function LeadForm({ language = "ar", onSubmit, onDismiss }) {
  const L = LABELS[language] || LABELS.ar;

  const [fields,     setFields]     = useState({ name: "", email: "", org: "", interest: "" });
  const [submitting, setSubmitting] = useState(false);
  const [done,       setDone]       = useState(false);

  const set = (key) => (e) => setFields((prev) => ({ ...prev, [key]: e.target.value }));

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!fields.name || !fields.email) return;
    setSubmitting(true);
    try {
      await onSubmit({ ...fields, language });
      setDone(true);
    } finally {
      setSubmitting(false);
    }
  };

  if (done) {
    return (
      <div className="lead-form">
        <p className="lead-form__title">
          {language === "ar" ? "شكراً! سيتواصل معك فريقنا قريباً." : "Thanks! Our team will be in touch soon."}
        </p>
      </div>
    );
  }

  return (
    <form className="lead-form" onSubmit={handleSubmit}>
      <p className="lead-form__title">{L.title}</p>

      <div className="lead-form__row">
        <input
          className="lead-form__input"
          placeholder={L.name}
          value={fields.name}
          onChange={set("name")}
          required
        />
        <input
          className="lead-form__input"
          type="email"
          placeholder={L.email}
          value={fields.email}
          onChange={set("email")}
          required
        />
      </div>

      <input
        className="lead-form__input"
        placeholder={L.org}
        value={fields.org}
        onChange={set("org")}
      />

      <input
        className="lead-form__input"
        placeholder={L.interest}
        value={fields.interest}
        onChange={set("interest")}
      />

      <button className="lead-form__submit" type="submit" disabled={submitting}>
        {L.submit}
      </button>

      <button type="button" className="lead-form__dismiss" onClick={onDismiss}>
        {L.dismiss}
      </button>
    </form>
  );
}
