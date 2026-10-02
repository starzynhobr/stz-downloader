import type { ReactNode } from 'react'
import type { Api, Disk, UpdateInfo } from '@/lib/bridge'
import { formatBytes } from '@/lib/format'
import { useI18n, type MessageKey } from '@/lib/i18n'
import { UpdateBanner } from './UpdateBanner'
import { AlertIcon, CheckIcon, ClockIcon, DownIcon, GearIcon, ListIcon, LogoMark } from './icons'

export type Filter = 'all' | 'active' | 'queued' | 'completed' | 'failed'

const FILTERS: { id: Filter; label: MessageKey; icon: ReactNode }[] = [
  { id: 'all', label: 'nav.all', icon: <ListIcon /> },
  { id: 'active', label: 'nav.active', icon: <DownIcon /> },
  { id: 'queued', label: 'nav.queued', icon: <ClockIcon /> },
  { id: 'completed', label: 'nav.completed', icon: <CheckIcon /> },
  { id: 'failed', label: 'nav.failed', icon: <AlertIcon /> },
]

interface Props {
  filter: Filter
  counts: Record<Filter, number>
  disk: Disk | undefined
  update: UpdateInfo | undefined
  api: Api
  onFilter: (f: Filter) => void
  onSettings: () => void
  settingsOpen: boolean
}

const item = (active: boolean) =>
  `flex h-9 items-center gap-2.5 rounded-lg px-2.5 text-left transition-colors ${
    active ? 'bg-raised text-ink-strong' : 'text-soft hover:bg-raised/60'
  }`

export function Sidebar({ filter, counts, disk, update, api, onFilter, onSettings, settingsOpen }: Props) {
  const { t } = useI18n()
  return (
    <aside className="flex w-[220px] shrink-0 flex-col gap-1 border-r border-line bg-rail px-3 py-5">
      <div className="flex items-center gap-2.5 px-2 pb-5">
        <div className="flex size-7 items-center justify-center rounded-lg bg-brand text-ground">
          <LogoMark />
        </div>
        <span className="text-sm font-semibold tracking-tight">STZ Downloader</span>
      </div>

      <nav aria-label={t('nav.filters')} className="flex flex-col gap-1">
        {FILTERS.map((f) => {
          const active = !settingsOpen && filter === f.id
          return (
            <button
              key={f.id}
              type="button"
              aria-current={active ? 'page' : undefined}
              onClick={() => onFilter(f.id)}
              className={item(active)}
            >
              {f.icon}
              <span className="grow truncate">{t(f.label)}</span>
              <span className={`font-mono text-xs ${f.id === 'failed' && counts.failed ? 'text-bad' : 'text-dim'}`}>
                {counts[f.id]}
              </span>
            </button>
          )
        })}
      </nav>

      <div className="grow" />

      {update && <UpdateBanner update={update} api={api} />}

      {disk?.available && disk.free !== undefined && (
        <div className="flex flex-col gap-1 rounded-[10px] bg-surface p-3 text-xs text-dim">
          <span className="truncate" title={disk.path}>
            {disk.path}
          </span>
          <span className={`font-mono ${disk.shortfall ? 'text-warn' : ''}`}>{t('disk.free', { size: formatBytes(disk.free) })}</span>
        </div>
      )}

      <button
        type="button"
        onClick={onSettings}
        aria-current={settingsOpen ? 'page' : undefined}
        className={`mt-2 ${item(settingsOpen)}`}
      >
        <GearIcon />
        {t('nav.settings')}
      </button>
    </aside>
  )
}
