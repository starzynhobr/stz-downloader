import { motion } from 'motion/react'
import { useState, type KeyboardEvent, type ReactNode } from 'react'
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip'
import { normalizeExtension } from '@/lib/extensions'
import { useI18n } from '@/lib/i18n'
import { CloseIcon } from './icons'

/** Icon-only button: the label is both its accessible name and its tooltip. */
export function IconButton({ label, onClick, children }: { label: string; onClick: () => void; children: ReactNode }) {
  return (
    <Tooltip>
      <TooltipTrigger
        render={
          <button
            type="button"
            aria-label={label}
            onClick={onClick}
            className="flex size-9 items-center justify-center rounded-lg text-soft transition-colors hover:bg-raised hover:text-ink-strong"
          />
        }
      >
        {children}
      </TooltipTrigger>
      <TooltipContent>{label}</TooltipContent>
    </Tooltip>
  )
}

export function Switch({ checked, label, onChange }: { checked: boolean; label: string; onChange: (v: boolean) => void }) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      aria-label={label}
      onClick={() => onChange(!checked)}
      className={`flex h-[26px] w-11 shrink-0 rounded-full p-[3px] transition-colors duration-200 ${
        checked ? 'justify-end bg-brand' : 'justify-start bg-edge'
      }`}
    >
      <motion.span layout transition={{ type: 'spring', stiffness: 600, damping: 34 }} className="size-5 rounded-full bg-ink-strong shadow-sm" />
    </button>
  )
}

/**
 * Chip editor for the captured file types. Enter, comma or space adds;
 * Backspace on an empty field removes the last chip.
 */
export function ExtensionEditor({ value, onChange }: { value: string[]; onChange: (next: string[]) => void }) {
  const { t } = useI18n()
  const [draft, setDraft] = useState('')
  const [invalid, setInvalid] = useState(false)

  const commit = () => {
    if (!draft.trim()) return
    const parts = draft.split(/[\s,;]+/).filter(Boolean)
    const valid = parts.map(normalizeExtension)
    if (valid.some((v) => v === null)) {
      setInvalid(true)
      return
    }
    const next = [...value]
    for (const ext of valid as string[]) if (!next.includes(ext)) next.push(ext)
    onChange(next)
    setDraft('')
  }

  const onKeyDown = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter' || e.key === ',' || e.key === ' ') {
      e.preventDefault()
      commit()
    } else if (e.key === 'Backspace' && !draft && value.length) {
      onChange(value.slice(0, -1))
    }
  }

  return (
    <div className="flex flex-col gap-2">
      <div
        className={`flex flex-wrap items-center gap-1.5 rounded-lg border bg-field p-2 transition-colors focus-within:border-brand ${
          invalid ? 'border-bad' : 'border-edge'
        }`}
      >
        {value.map((ext) => (
          <motion.span
            key={ext}
            layout
            initial={{ opacity: 0, scale: 0.8 }}
            animate={{ opacity: 1, scale: 1 }}
            className="flex h-7 items-center gap-1 rounded-md bg-raised pl-2 pr-1 font-mono text-xs text-soft"
          >
            {ext}
            <button
              type="button"
              aria-label={t('ext.remove', { ext })}
              onClick={() => onChange(value.filter((v) => v !== ext))}
              className="flex size-5 items-center justify-center rounded text-faint hover:bg-edge hover:text-ink"
            >
              <CloseIcon size={12} />
            </button>
          </motion.span>
        ))}
        <input
          value={draft}
          onChange={(e) => {
            setDraft(e.target.value)
            setInvalid(false)
          }}
          onKeyDown={onKeyDown}
          onBlur={commit}
          aria-label={t('ext.add')}
          aria-invalid={invalid}
          placeholder={value.length ? t('ext.more') : t('ext.empty')}
          className="h-7 min-w-24 grow bg-transparent px-1 font-mono text-xs text-ink outline-none placeholder:font-sans placeholder:text-faint"
        />
      </div>
      <span className={`text-xs ${invalid ? 'text-bad' : 'text-dim'}`}>
        {invalid ? t('ext.invalid') : t('ext.hint')}
      </span>
    </div>
  )
}
