import { motion } from 'motion/react'
import { useEffect, useRef, useState } from 'react'
import type { Api, Pending, Settings } from '@/lib/bridge'
import { fileBadge, formatBytes, hostOf } from '@/lib/format'
import { useI18n } from '@/lib/i18n'
import { CloseIcon } from './icons'

const STEPS = [1, 4, 8, 12, 16]

interface Props {
  pending: Pending
  remaining: number
  settings: Settings
  api: Api
}

/** Confirmation for a browser download, shown while auto-start is off. */
export function NewDownloadDialog({ pending, remaining, settings, api }: Props) {
  const { t } = useI18n()
  const [name, setName] = useState(pending.name)
  const [connections, setConnections] = useState(settings.connections)
  const [autoNext, setAutoNext] = useState(false)
  const dialog = useRef<HTMLDialogElement>(null)
  const nameField = useRef<HTMLInputElement>(null)

  useEffect(() => {
    if (!dialog.current?.open) dialog.current?.showModal()
    // showModal() focuses the first button (Close); the name is what you
    // would actually want to edit.
    nameField.current?.focus()
  }, [])

  const confirm = async () => {
    if (autoNext) await api('/api/settings', { method: 'PUT', body: { auto_start: true } })
    await api(`/api/pending/${pending.id}/confirm`, { method: 'POST', body: { connections, filename: name } })
  }
  const dismiss = () => api(`/api/pending/${pending.id}/cancel`, { method: 'POST' })

  return (
    <dialog
      ref={dialog}
      aria-labelledby="nd-title"
      onCancel={(e) => {
        e.preventDefault()
        dismiss()
      }}
      className="m-auto w-[520px] overflow-visible bg-transparent p-0 text-ink backdrop:bg-black/60 backdrop:backdrop-blur-[2px]"
    >
      <motion.div
        initial={{ opacity: 0, scale: 0.96, y: 8 }}
        animate={{ opacity: 1, scale: 1, y: 0 }}
        transition={{ type: 'spring', stiffness: 420, damping: 32 }}
        className="rounded-2xl border border-edge bg-surface shadow-[0_24px_64px_rgba(0,0,0,0.55)]"
      >
      <div className="flex items-center gap-3.5 border-b border-line px-6 pb-4 pt-5">
        <div className="flex size-11 shrink-0 items-center justify-center rounded-[10px] bg-raised font-mono text-[11px] font-medium">
          {fileBadge(pending.name)}
        </div>
        <div className="flex min-w-0 grow flex-col gap-1">
          <h2 id="nd-title" className="m-0 text-[15px] font-semibold">
            {t('dialog.title')}
            {remaining > 1 ? ` · ${t('dialog.waiting', { n: remaining })}` : ''}
          </h2>
          <span className="truncate text-xs text-dim">
            {hostOf(pending.url)} · {pending.size ? formatBytes(pending.size) : t('dialog.sizeUnknown')}
          </span>
        </div>
        <button
          type="button"
          aria-label={t('dialog.close')}
          onClick={dismiss}
          className="flex size-9 items-center justify-center rounded-lg text-dim hover:bg-raised hover:text-ink"
        >
          <CloseIcon />
        </button>
      </div>

      <div className="flex flex-col gap-4 px-6 py-5">
        <label className="flex flex-col gap-1.5">
          <span className="text-xs text-dim">{t('dialog.fileName')}</span>
          <input
            ref={nameField}
            value={name}
            onChange={(e) => setName(e.target.value)}
            className="h-10 rounded-lg border border-edge bg-field px-3 text-[13px] text-ink outline-none focus:border-brand"
          />
        </label>

        <div className="flex flex-col gap-2">
          <div className="flex justify-between text-xs">
            <span className="text-dim">{t('dialog.connections')}</span>
            <span className="font-mono">{connections}</span>
          </div>
          <div role="radiogroup" aria-label={t('dialog.connections')} className="flex gap-1">
            {STEPS.map((n) => (
              <button
                key={n}
                type="button"
                role="radio"
                aria-checked={connections === n}
                onClick={() => setConnections(n)}
                className={`h-9 grow rounded-lg border font-mono text-xs transition-colors ${
                  connections === n
                    ? 'border-brand bg-brand text-on-brand'
                    : 'border-edge bg-field text-soft hover:border-faint'
                }`}
              >
                {n}
              </button>
            ))}
          </div>
          <span className="text-xs text-dim">{t('dialog.connectionsHint')}</span>
        </div>

        <label className="flex min-h-11 cursor-pointer items-center gap-2.5">
          <input
            type="checkbox"
            checked={autoNext}
            onChange={(e) => setAutoNext(e.target.checked)}
            className="checkbox m-0"
          />
          <span className="flex flex-col gap-0.5">
            <span>{t('dialog.autoNext')}</span>
            <span className="text-xs text-dim">{t('dialog.autoNextHint')}</span>
          </span>
        </label>
      </div>

      <div className="flex justify-end gap-2 border-t border-line px-6 py-4">
        <button
          type="button"
          onClick={dismiss}
          className="h-10 rounded-lg border border-edge px-4 text-[13px] text-soft hover:bg-raised"
        >
          {t('dialog.cancel')}
        </button>
        <button
          type="button"
          onClick={confirm}
          className="h-10 rounded-lg bg-brand px-5 text-[13px] font-semibold text-on-brand hover:brightness-110"
        >
          {t('dialog.start')}
        </button>
      </div>
      </motion.div>
    </dialog>
  )
}
