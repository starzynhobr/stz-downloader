import { AnimatePresence, motion } from 'motion/react'
import { useMemo, useState, type FormEvent } from 'react'
import { DownloadRow } from '@/components/DownloadRow'
import { LinkIcon } from '@/components/icons'
import { NewDownloadDialog } from '@/components/NewDownloadDialog'
import { SettingsView } from '@/components/SettingsView'
import { Sidebar, type Filter } from '@/components/Sidebar'
import { TooltipProvider } from '@/components/ui/tooltip'
import { isReconnecting, useBridge, type Download } from '@/lib/bridge'
import { formatSpeed } from '@/lib/format'
import { useI18n, type MessageKey } from '@/lib/i18n'
import { I18nProvider } from '@/lib/I18nProvider'

const MATCHES: Record<Filter, (d: Download) => boolean> = {
  all: () => true,
  active: (d) => d.status === 'active' || isReconnecting(d),
  queued: (d) => d.status === 'waiting' || d.status === 'paused',
  completed: (d) => d.status === 'complete',
  failed: (d) => d.status === 'error' && !isReconnecting(d),
}

const TITLES: Record<Filter, MessageKey> = {
  all: 'nav.all',
  active: 'nav.active',
  queued: 'nav.queued',
  completed: 'nav.completed',
  failed: 'nav.failed',
}

const fade = {
  initial: { opacity: 0, y: 8 },
  animate: { opacity: 1, y: 0 },
  exit: { opacity: 0, y: -8 },
  transition: { duration: 0.16 },
}

export default function App() {
  return (
    <I18nProvider>
      <TooltipProvider delay={400}>
        <Shell />
      </TooltipProvider>
    </I18nProvider>
  )
}

function Shell() {
  const { t } = useI18n()
  const { snapshot, connection, api, updateSettings } = useBridge()
  const [filter, setFilter] = useState<Filter>('all')
  const [settingsOpen, setSettingsOpen] = useState(false)
  const [url, setUrl] = useState('')

  const items = useMemo(() => snapshot?.items ?? [], [snapshot])
  const counts = useMemo(
    () =>
      Object.fromEntries((Object.keys(MATCHES) as Filter[]).map((f) => [f, items.filter(MATCHES[f]).length])) as Record<
        Filter,
        number
      >,
    [items],
  )
  const visible = items.filter(MATCHES[filter])
  const pending = snapshot?.pending ?? []

  const add = async (e: FormEvent) => {
    e.preventDefault()
    const link = url.trim()
    if (!link) return
    await api('/api/download', { method: 'POST', body: { url: link } })
    setUrl('')
    setFilter('all')
  }

  if (!snapshot) {
    return (
      <div className="flex h-full items-center justify-center text-dim">
        {connection === 'offline' ? t('boot.starting') : t('boot.connecting')}
      </div>
    )
  }

  return (
    <div className="flex h-full overflow-hidden">
      <Sidebar
        filter={filter}
        counts={counts}
        disk={snapshot.disk}
        update={snapshot.update}
        api={api}
        settingsOpen={settingsOpen}
        onFilter={(f) => {
          setFilter(f)
          setSettingsOpen(false)
        }}
        onSettings={() => setSettingsOpen(true)}
      />

      <main className="flex min-w-0 grow flex-col">
        <AnimatePresence mode="wait" initial={false}>
          {settingsOpen ? (
            <motion.div key="settings" {...fade} className="min-h-0 grow">
              <SettingsView settings={snapshot.settings} update={snapshot.update} onChange={updateSettings} api={api} />
            </motion.div>
          ) : (
            <motion.div key="queue" {...fade} className="flex min-h-0 grow flex-col">
              <form onSubmit={add} className="flex items-center gap-3 px-7 pb-4 pt-5">
                <label className="flex h-11 grow items-center gap-2.5 rounded-[10px] border border-edge bg-surface px-3.5 focus-within:border-brand">
                  <LinkIcon className="text-faint" />
                  <input
                    value={url}
                    onChange={(e) => setUrl(e.target.value)}
                    placeholder={t('queue.placeholder')}
                    aria-label={t('queue.link')}
                    className="grow bg-transparent text-[13px] text-ink outline-none placeholder:text-faint"
                  />
                </label>
                <button
                  type="submit"
                  disabled={!url.trim()}
                  className="h-11 rounded-[10px] bg-brand px-5 text-[13px] font-semibold text-on-brand transition hover:brightness-110 disabled:opacity-40"
                >
                  {t('queue.download')}
                </button>
              </form>

              <div className="flex items-center gap-2 px-7 pb-2.5">
                <span className="grow text-[15px] font-medium">{t(TITLES[filter])}</span>
                <button
                  type="button"
                  onClick={() => api('/api/downloads/purge', { method: 'POST' })}
                  disabled={!counts.completed && !counts.failed}
                  className="h-8 rounded-lg border border-edge px-3 text-xs text-soft hover:bg-raised disabled:opacity-40"
                >
                  {t('queue.clearFinished')}
                </button>
              </div>

              <div className="grid grid-cols-[1fr_130px_110px_80px_136px] items-center gap-4 border-b border-line px-7 py-2 text-[11px] uppercase tracking-wider text-faint">
                <span>{t('queue.name')}</span>
                <span>{t('queue.size')}</span>
                <span>{t('queue.speed')}</span>
                <span>{t('queue.timeLeft')}</span>
                <span />
              </div>

              {visible.length ? (
                <ul className="m-0 grow list-none overflow-y-auto p-0">
                  <AnimatePresence initial={false}>
                    {visible.map((d) => (
                      <DownloadRow key={d.gid} d={d} api={api} />
                    ))}
                  </AnimatePresence>
                </ul>
              ) : (
                <div className="flex grow flex-col items-center justify-center gap-1 text-center text-dim">
                  <span className="text-ink">{filter === 'all' ? t('queue.emptyTitle') : t('queue.emptyFiltered')}</span>
                  {filter === 'all' && <span>{t('queue.emptyHint')}</span>}
                </div>
              )}
            </motion.div>
          )}
        </AnimatePresence>

        <footer className="flex h-[52px] shrink-0 items-center gap-5 border-t border-line bg-rail px-7 text-xs text-dim">
          <span className="flex items-center gap-2">
            <span className={`size-1.5 rounded-full ${connection === 'online' ? 'bg-ok' : 'bg-warn'}`} />
            {connection === 'online' ? t('footer.running') : t('footer.reconnecting')}
          </span>
          <span className="grow" />
          <span>{t('footer.active', { n: snapshot.global.numActive })}</span>
          <span className="font-mono text-ink">↓ {formatSpeed(snapshot.global.downloadSpeed)}</span>
        </footer>
      </main>

      {pending[0] && (
        <NewDownloadDialog
          key={pending[0].id}
          pending={pending[0]}
          remaining={pending.length}
          settings={snapshot.settings}
          api={api}
        />
      )}
    </div>
  )
}
