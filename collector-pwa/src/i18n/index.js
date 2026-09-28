import i18n from 'i18next'
import { initReactI18next } from 'react-i18next'

import en from './en.json'
import hi from './hi.json'
import mr from './mr.json'

const stored = localStorage.getItem('kc_lang') || 'hi'

i18n.use(initReactI18next).init({
  resources: {
    en: { translation: en },
    hi: { translation: hi },
    mr: { translation: mr }
  },
  lng: stored,
  fallbackLng: 'en',
  interpolation: { escapeValue: false }
})

export function setLanguage(lang) {
  localStorage.setItem('kc_lang', lang)
  i18n.changeLanguage(lang)
}

export default i18n
