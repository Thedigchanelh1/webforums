import i18n from 'i18next'
import { initReactI18next } from 'react-i18next'
import en from './locales/en.json'
import es from './locales/es.json'
import fr from './locales/fr.json'
import hi from './locales/hi.json'

i18n.use(initReactI18next).init({
  resources: { en: { translation: en }, es: { translation: es }, fr: { translation: fr }, hi: { translation: hi } },
  lng: localStorage.getItem('fi_lang') || 'en',
  fallbackLng: 'en',
  interpolation: { escapeValue: false },
})

export function setLanguage(code) {
  localStorage.setItem('fi_lang', code)
  i18n.changeLanguage(code)
}

export default i18n
