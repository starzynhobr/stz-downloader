import { motion } from 'motion/react'
import { isReconnecting, type Api, type Download } from '@/lib/bridge'
import { fileBadge, formatBytes, formatDuration, formatSpeed } from '@/lib/format'
import { useI18n, type MessageKey, type Translate } from '@/lib/i18n'
import { IconButton } from './controls'
import { CloseIcon, FolderIcon, OpenIcon, PauseIcon, PlayIcon, RetryIcon } from './icons'
import { SpeedLimitPopover } from './SpeedLimitPopover'

interface View {
  label: string
  tone: string
  bar: string
}

/** aria2 exit codes worth a translated explanation; others show aria2's text. */
const ERROR_KEYS: Record<string, MessageKey> = {
  '3': 'error.notFound',
  '9': 'error.diskFull',
  '13': 'error.exists',
  '24': 'error.auth',
  '22': 'error.server',
  '2': 'error.network',
  '6': 'error.network',
  '19': 'error.network',
}

function errorText(d: Download, t: Translate): string {
  if (/403/.test(d.error)) return t('error.forbidden')
  const key = ERROR_KEYS[d.errorCode]
  return key ? t(key) : d.error
}

function describe(d: Download, t: Translate): View {
  const v = (key: MessageKey, tone: string, bar: string) => ({ label: t(key), tone, bar })
  if (isReconnecting(d)) return v('status.reconnecting', 'text-warn', 'bg-warn')
  switch (d.status) {
    case 'active':
      return v(d.speed > 0 ? 'status.downloading' : 'status.connecting', 'text-brand', 'bg-brand')
    case 'waiting':
      return v('status.queued', 'text-dim', 'bg-faint')
    case 'paused':
      return v('status.paused', 'text-dim', 'bg-faint')
    case 'complete':
      return v('status.completed', 'text-ok', 'bg-ok/50')
    case 'removed':
      return v('status.cancelled', 'text-faint', 'bg-edge')
    default: {
      const why = errorText(d, t)
      return { label: why ? `${t('status.failed')} · ${why}` : t('status.failed'), tone: 'text-bad', bar: 'bg-bad' }
    }
  }
}

export function DownloadRow({ d, api }: { d: Download; api: Api }) {
  const { t } = useI18n()
  const view = describe(d, t)
  const act = (action: string) => () => api(`/api/downloads/${d.gid}/${action}`, { method: 'POST' }).catch(console.error)
  const pct = d.total ? Math.min(100, (d.completed / d.total) * 100) : 0
  const running = d.status === 'active'
  const unfinished = running || d.status === 'paused' || d.status === 'waiting'
  const finished = d.status === 'complete' || d.status === 'removed' || d.status === 'error'
  const eta = running && d.speed > 0 && d.total > d.completed ? (d.total - d.completed) / d.speed : 0

  return (
    <motion.li
      layout
      initial={{ opacity: 0, y: -6 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, x: 24, transition: { duration: 0.18 } }}
      transition={{ type: 'spring', stiffness: 500, damping: 40 }}
      className="group grid grid-cols-[1fr_130px_110px_80px_136px] items-center gap-4 border-b border-line/70 px-7 py-3.5 hover:bg-surface/60"
    >
      <div className="flex min-w-0 items-center gap-3">
        <div className="flex size-9 shrink-0 items-center justify-center rounded-lg bg-raised font-mono text-[10px] font-medium text-soft">
          {fileBadge(d.name)}
        </div>
        <div className="flex min-w-0 grow flex-col gap-1.5">
          <span className="truncate font-medium" title={d.name}>
            {d.name || t('queue.gettingName')}
          </span>
          <div className="flex items-center gap-2.5">
            <div className="h-1 grow rounded-full bg-track">
              <div className={`h-1 rounded-full ${view.bar} transition-[width] duration-500`} style={{ width: `${pct}%` }} />
            </div>
            <span className={`flex max-w-[65%] items-center gap-1.5 truncate text-xs ${view.tone}`} title={view.label}>
              <span className="size-1.5 shrink-0 rounded-full bg-current" />
              <span className="truncate">{view.label}</span>
            </span>
          </div>
        </div>
      </div>

      <span className="font-mono text-xs text-soft">
        {d.total ? (d.status === 'complete' ? formatBytes(d.total) : `${formatBytes(d.completed)} / ${formatBytes(d.total)}`) : '—'}
      </span>
      <span className="flex flex-col font-mono text-xs">
        <span>{running && d.speed > 0 ? formatSpeed(d.speed) : '—'}</span>
        {d.speedLimit > 0 && unfinished && <span className="text-[11px] text-brand">≤ {formatSpeed(d.speedLimit)}</span>}
      </span>
      <span className="font-mono text-xs text-soft">{formatDuration(eta)}</span>

      <div className="flex justify-end gap-1">
        {unfinished && <SpeedLimitPopover gid={d.gid} limit={d.speedLimit} api={api} />}
        {running && (
          <IconButton label={t('action.pause')} onClick={act('pause')}>
            <PauseIcon />
          </IconButton>
        )}
        {(d.status === 'paused' || d.status === 'waiting') && (
          <IconButton label={t('action.resume')} onClick={act('resume')}>
            <PlayIcon />
          </IconButton>
        )}
        {(d.status === 'removed' || (d.status === 'error' && !isReconnecting(d))) && (
          <IconButton label={t('action.restart')} onClick={act('restart')}>
            <RetryIcon />
          </IconButton>
        )}
        {d.status === 'complete' && (
          <>
            <IconButton label={t('action.open')} onClick={act('open')}>
              <OpenIcon />
            </IconButton>
            <IconButton label={t('action.reveal')} onClick={act('reveal')}>
              <FolderIcon />
            </IconButton>
          </>
        )}
        <IconButton label={finished ? t('action.remove') : t('action.cancel')} onClick={act('cancel')}>
          <CloseIcon />
        </IconButton>
      </div>
    </motion.li>
  )
}
