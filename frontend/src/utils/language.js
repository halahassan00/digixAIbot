/**
 * src/utils/language.js
 *
 * Switches UI text direction between RTL (Arabic) and LTR (English).
 * Called whenever the detected language changes.
 */

/**
 * Return the CSS direction for a given language code.
 * @param {string} language  "ar" | "en"
 * @returns {"rtl" | "ltr"}
 */
export function getDirection(language) {
  return language === "ar" ? "rtl" : "ltr";
}

/**
 * Apply direction and lang attribute to the chat container element.
 * @param {HTMLElement} el
 * @param {string} language  "ar" | "en"
 */
export function applyDirection(el, language) {
  if (!el) return;
  el.dir  = getDirection(language);
  el.lang = language;
}
