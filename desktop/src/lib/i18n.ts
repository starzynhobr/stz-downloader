import { createContext, useContext } from 'react'
import { LANGUAGES, type Language, type MessageKey } from './messages'

export type { Language, MessageKey } from './messages'

export const STORAGE_KEY = 'stz.language'

export function initialLanguage(): Language {
  try {
    const saved = localStorage.getItem(STORAGE_KEY)
    if (saved && LANGUAGES.some((l) => l.code === saved)) return saved as Language
  } catch {
    /* storage unavailable */
  }
  const system = navigator.language.slice(0, 2).toLowerCase()
  return (LANGUAGES.find((l) => l.code === system)?.code ?? 'en') as Language
}

export type Translate = (key: MessageKey, vars?: Record<string, string | number>) => string

export interface I18n {
  language: Language
  setLanguage: (l: Language) => void
  t: Translate
}

export const I18nContext = createContext<I18n | null>(null)

export function useI18n(): I18n {
  const ctx = useContext(I18nContext)
  if (!ctx) throw new Error('useI18n outside I18nProvider')
  return ctx
}
