import { useState, type ReactNode } from 'react'
import type { Api, Settings, UpdateInfo } from '@/lib/bridge'
import { useI18n, type Language } from '@/lib/i18n'
import { LANGUAGES } from '@/lib/messages'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { ExtensionEditor, Switch } from './controls'

const MB = 1024 * 1024
const LIMITS = [0, 1, 5, 10, 25]

function Row({ title, hint, children }: { title: string; hint?: string; children: ReactNode }) {
  return (
    <div className="flex items-center gap-4 border-b border-line px-5 py-4 last:border-b-0">
      <div className="flex grow flex-col gap-0.5">
        <span className="font-medium">{title}</span>
        {hint && <span className="text-xs text-dim">{hint}</span>}
      </div>
      {children}
    </div>
  )
}

function Card({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="flex flex-col gap-2">
      <h2 className="m-0 px-1 text-xs font-medium uppercase tracking-wider text-faint">{title}</h2>
      <div className="rounded-xl border border-line bg-surface">{children}</div>
    </section>
  )
}

interface Props {
  settings: Settings
  update: UpdateInfo | undefined
  api: Api
  onChange: (patch: Partial<Settings>) => Promise<void>
}

export function SettingsView({ settings, update, api, onChange }: Props) {
  const { t, language, setLanguage } = useI18n()
  const [check, setCheck] = useState<'idle' | 'checking' | 'done'>('idle')
  const checkNow = async () => {
    setCheck('checking')
    await api('/api/update/check', { method: 'POST' }).catch(console.error)
    setCheck('done')
  }
  const checkResult =
    check === 'checking'
      ? t('settings.checking')
      : check === 'done' && update
        ? update.status === 'error'
          ? t('settings.checkFailed')
          : update.available
            ? t('update.available', { v: update.version })
            : t('settings.upToDate')
        : undefined
  const set = (patch: Partial<Settings>) => onChange(patch).catch(console.error)

  return (
    <div className="flex h-full flex-col overflow-y-auto">
      <div className="flex w-full max-w-[760px] flex-col gap-7 px-12 py-8">
        <div className="flex flex-col gap-1.5">
          <h1 className="m-0 text-[22px] font-semibold tracking-tight">{t('settings.title')}</h1>
          <p className="m-0 text-dim">{t('settings.subtitle')}</p>
        </div>

        <Card title={t('settings.downloads')}>
          <Row title={t('settings.connections')} hint={t('settings.connectionsHint')}>
            <div className="flex items-center overflow-hidden rounded-lg border border-edge">
              <button
                type="button"
                aria-label={t('settings.fewer')}
                onClick={() => set({ connections: Math.max(1, settings.connections - 1) })}
                className="h-9 w-10 bg-raised text-base text-soft hover:text-ink"
              >
                −
              </button>
              <span className="w-11 text-center font-mono">{settings.connections}</span>
              <button
                type="button"
                aria-label={t('settings.more')}
                onClick={() => set({ connections: Math.min(16, settings.connections + 1) })}
                className="h-9 w-10 bg-raised text-base text-soft hover:text-ink"
              >
                +
              </button>
            </div>
          </Row>
          <div className="flex flex-col gap-3 border-b border-line px-5 py-4">
            <div className="flex flex-col gap-0.5">
              <span className="font-medium">{t('settings.totalLimit')}</span>
              <span className="text-xs text-dim">{t('settings.totalLimitHint')}</span>
            </div>
            <div role="radiogroup" aria-label={t('settings.totalLimit')} className="flex gap-1">
              {LIMITS.map((mb) => {
                const on = settings.download_limit_bps === mb * MB
                return (
                  <button
                    key={mb}
                    type="button"
                    role="radio"
                    aria-checked={on}
                    onClick={() => set({ download_limit_bps: mb * MB })}
                    className={`h-9 grow rounded-lg border text-xs transition-colors ${
                      on ? 'border-brand bg-brand text-on-brand' : 'border-edge bg-field text-soft hover:border-faint'
                    }`}
                  >
                    {mb === 0 ? t('limit.unlimited') : `${mb} MB/s`}
                  </button>
                )
              })}
            </div>
          </div>
          <Row title={t('settings.diskGuard')} hint={t('settings.diskGuardHint', { gb: Math.round(settings.disk_reserve_mb / 1024) })}>
            <Switch label={t('settings.diskGuard')} checked={settings.disk_guard_enabled} onChange={(v) => set({ disk_guard_enabled: v })} />
          </Row>
        </Card>

        <Card title={t('settings.capture')}>
          <Row title={t('settings.captureOn')} hint={t('settings.captureOnHint')}>
            <Switch label={t('settings.captureOn')} checked={settings.intercept_enabled} onChange={(v) => set({ intercept_enabled: v })} />
          </Row>
          <Row title={t('settings.autoStart')} hint={t('settings.autoStartHint')}>
            <Switch label={t('settings.autoStart')} checked={settings.auto_start} onChange={(v) => set({ auto_start: v })} />
          </Row>
          <Row title={t('settings.clipboard')} hint={t('settings.clipboardHint')}>
            <Switch label={t('settings.clipboard')} checked={settings.clipboard_enabled} onChange={(v) => set({ clipboard_enabled: v })} />
          </Row>
          <Row title={t('settings.captureAll')} hint={t('settings.captureAllHint')}>
            <Switch label={t('settings.captureAll')} checked={settings.intercept_all} onChange={(v) => set({ intercept_all: v })} />
          </Row>
          <div className={`flex flex-col gap-3 px-5 py-4 transition-opacity ${settings.intercept_all ? 'opacity-50' : ''}`}>
            <div className="flex flex-col gap-0.5">
              <span className="font-medium">{t('settings.fileTypes')}</span>
              <span className="text-xs text-dim">
                {settings.intercept_all ? t('settings.fileTypesUnused') : t('settings.fileTypesHint')}
              </span>
            </div>
            <ExtensionEditor value={settings.extensions} onChange={(extensions) => set({ extensions })} />
          </div>
        </Card>

        <Card title={t('settings.app')}>
          <Row title={t('settings.language')}>
            <Select
              items={LANGUAGES.map((l) => ({ value: l.code, label: l.name }))}
              value={language}
              onValueChange={(v) => v && setLanguage(v as Language)}
            >
              <SelectTrigger
                aria-label={t('settings.language')}
                className="h-9 min-w-36 border-edge bg-raised px-3 text-[13px] text-ink hover:bg-edge/60 focus-visible:ring-2 focus-visible:ring-brand/60"
              >
                <SelectValue />
              </SelectTrigger>
              <SelectContent className="border border-edge bg-raised p-1">
                {LANGUAGES.map((l) => (
                  <SelectItem key={l.code} value={l.code} className="h-8 px-2 text-[13px] text-soft focus:bg-edge focus:text-ink-strong">
                    {l.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </Row>
          <Row title={t('settings.updates')} hint={t('settings.updatesHint')}>
            <Switch label={t('settings.updates')} checked={settings.auto_update_check} onChange={(v) => set({ auto_update_check: v })} />
          </Row>
          <Row title={t('settings.version', { v: update?.current ?? '' })} hint={checkResult}>
            <button
              type="button"
              onClick={checkNow}
              disabled={check === 'checking'}
              className="h-9 rounded-lg border border-edge bg-raised px-3 text-xs text-soft hover:text-ink disabled:opacity-50"
            >
              {t('settings.checkNow')}
            </button>
          </Row>
          <Row title={t('settings.startWindows')} hint={t('settings.startWindowsHint')}>
            <Switch label={t('settings.startWindows')} checked={settings.start_with_windows} onChange={(v) => set({ start_with_windows: v })} />
          </Row>
        </Card>
      </div>
    </div>
  )
}
