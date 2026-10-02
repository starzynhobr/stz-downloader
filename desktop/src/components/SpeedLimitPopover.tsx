import { useState, type FormEvent } from 'react'
import { Popover, PopoverContent, PopoverDescription, PopoverTitle, PopoverTrigger } from '@/components/ui/popover'
import type { Api } from '@/lib/bridge'
import { useI18n } from '@/lib/i18n'
import { GaugeIcon } from './icons'

const MB = 1024 * 1024
const PRESETS = [0, 1, 5, 10, 25]

/** Per-download cap; zero removes it, matching aria2's option semantics. */
export function SpeedLimitPopover({ gid, limit, api }: { gid: string; limit: number; api: Api }) {
  const { t } = useI18n()
  const [open, setOpen] = useState(false)
  const [custom, setCustom] = useState('')

  const apply = (bytesPerSecond: number) =>
    api(`/api/downloads/${gid}/speed-limit`, { method: 'POST', body: { bytes_per_second: bytesPerSecond } })
      .then(() => setOpen(false))
      .catch(console.error)

  const submitCustom = (e: FormEvent) => {
    e.preventDefault()
    const value = Number(custom.replace(',', '.'))
    if (Number.isFinite(value) && value >= 0) apply(Math.round(value * MB))
  }

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger
        render={
          <button
            type="button"
            aria-label={t('action.limit')}
            title={t('action.limit')}
            className={`flex size-9 items-center justify-center rounded-lg transition-colors hover:bg-raised hover:text-ink-strong ${
              limit > 0 ? 'text-brand' : 'text-soft'
            }`}
          />
        }
      >
        <GaugeIcon />
      </PopoverTrigger>
      <PopoverContent align="end" className="w-80 gap-3 border border-edge bg-raised p-4">
        <div className="flex flex-col gap-1">
          <PopoverTitle className="text-[13px] font-semibold">{t('limit.title')}</PopoverTitle>
          <PopoverDescription className="text-xs text-dim">{t('limit.hint')}</PopoverDescription>
        </div>
        <div role="radiogroup" aria-label={t('action.limit')} className="grid grid-cols-5 gap-1">
          {PRESETS.map((mb) => {
            const on = limit === mb * MB
            return (
              <button
                key={mb}
                type="button"
                role="radio"
                aria-checked={on}
                onClick={() => apply(mb * MB)}
                className={`h-9 rounded-lg border text-xs transition-colors ${
                  on ? 'border-brand bg-brand text-on-brand' : 'border-edge bg-field text-soft hover:border-faint'
                }`}
              >
                {mb === 0 ? '∞' : mb}
              </button>
            )
          })}
        </div>
        <form onSubmit={submitCustom} className="flex gap-2">
          <label className="flex grow flex-col gap-1">
            <span className="text-xs text-dim">{t('limit.custom')}</span>
            <input
              inputMode="decimal"
              value={custom}
              onChange={(e) => setCustom(e.target.value)}
              placeholder={limit > 0 ? String(+(limit / MB).toFixed(2)) : t('limit.unlimited')}
              className="h-9 rounded-lg border border-edge bg-field px-3 font-mono text-xs text-ink outline-none focus:border-brand"
            />
          </label>
          <button
            type="submit"
            disabled={!custom.trim()}
            className="h-9 self-end rounded-lg bg-brand px-3 text-xs font-semibold text-on-brand disabled:opacity-40"
          >
            {t('limit.apply')}
          </button>
        </form>
      </PopoverContent>
    </Popover>
  )
}
