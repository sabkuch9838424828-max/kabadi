/**
 * Voice-based price board using the browser-native Web Speech API.
 *
 * No external API / cost: the browser synthesises speech, and the text is
 * localised, so a low-literacy collector can hear today's rates in Hindi,
 * Marathi or English (documentation Pillar 3).
 */
import i18n from '../i18n'

const LANG_TAG = { hi: 'hi-IN', mr: 'mr-IN', en: 'en-IN' }

export function speechSupported() {
  return typeof window !== 'undefined' && 'speechSynthesis' in window
}

export function speak(text, lang) {
  if (!speechSupported()) return false
  const tag = LANG_TAG[lang || i18n.language] || 'hi-IN'
  window.speechSynthesis.cancel()
  const utter = new SpeechSynthesisUtterance(text)
  utter.lang = tag
  utter.rate = 0.95
  const match = window.speechSynthesis.getVoices().find((v) => v.lang === tag)
  if (match) utter.voice = match
  window.speechSynthesis.speak(utter)
  return true
}

export function stopSpeaking() {
  if (speechSupported()) window.speechSynthesis.cancel()
}

/** Speech recognition for optional voice search of a category. */
export function listenOnce({ lang, onResult, onError } = {}) {
  const SR = window.SpeechRecognition || window.webkitSpeechRecognition
  if (!SR) {
    onError?.(new Error('Speech recognition not supported on this device'))
    return null
  }
  const recognition = new SR()
  recognition.lang = LANG_TAG[lang || i18n.language] || 'hi-IN'
  recognition.interimResults = false
  recognition.maxAlternatives = 1
  recognition.onresult = (event) => {
    onResult?.(event.results[0][0].transcript)
  }
  recognition.onerror = (event) => onError?.(new Error(event.error))
  recognition.start()
  return recognition
}

export function boardToSpeech(entries, t) {
  const parts = entries
    .filter((e) => Number(e.best_price) > 0)
    .slice(0, 8)
    .map((e) => {
      const name = t(`category.${e.material_category}`)
      const trend = t(`prices.trend.${e.trend}`)
      return `${name}: ${Number(e.best_price).toFixed(0)} rupaye per kilo, ${trend}`
    })
  return parts.join('. ')
}
