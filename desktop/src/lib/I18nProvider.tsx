import { useCallback, useEffect, useMemo, useState, type ReactNode } from 'react'
import { I18nContext, initialLanguage, STORAGE_KEY, type I18n } from './i18n'
import { en, LANGUAGES, type Dictionary, type Language } from './messages'

export function I18nProvider({ children }: { children: ReactNode }) {
  const [language, setLanguageState] = useState<Language>(initialLanguage)

  const setLanguage = useCallback((l: Language) => {
    setLanguageState(l)
    try {
      localStorage.setItem(STORAGE_KEY, l)
    } catch {
      /* storage unavailable */
    }
  }, [])

  const value = useMemo<I18n>(() => {
    const dict: Dictionary = LANGUAGES.find((l) => l.code === language)?.dict ?? en
    return {
      language,
      setLanguage,
      t: (key, vars) => {
        let text = dict[key] ?? en[key]
        if (vars) for (const [k, v] of Object.entries(vars)) text = text.replace(`{${k}}`, String(v))
        return text
      },
    }
  }, [language, setLanguage])

  useEffect(() => {
    document.documentElement.lang = language
  }, [language])

  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>
}
