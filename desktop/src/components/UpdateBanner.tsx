import { openUrl } from '@tauri-apps/plugin-opener'
import { AnimatePresence, motion } from 'motion/react'
import type { Api, UpdateInfo } from '@/lib/bridge'
import { useI18n } from '@/lib/i18n'

/** Sidebar card that appears only when there is a newer release. */
export function UpdateBanner({ update, api }: { update: UpdateInfo; api: Api }) {
  const { t } = useI18n()
  const busy = update.status === 'downloading' || update.status === 'verifying' || update.status === 'installing'
  const show = update.available || busy

  const install = () => api('/api/update/install', { method: 'POST' }).catch(console.error)
  const notes = () => update.page_url && openUrl(update.page_url).catch(console.error)

  return (
    <AnimatePresence>
      {show && (
        <motion.div
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: 8 }}
          role="status"
          className="mb-2 flex flex-col gap-2 rounded-[10px] border border-brand/40 bg-brand/10 p-3 text-xs"
        >
          <span className="font-medium text-ink-strong">{t('update.available', { v: update.version })}</span>

          {busy ? (
            <>
              <span className="text-soft">
                {update.status === 'downloading'
                  ? t('update.downloading', { p: Math.round(update.progress * 100) })
                  : update.status === 'verifying'
                    ? t('update.verifying')
                    : t('update.installing')}
              </span>
              <div className="h-1 rounded-full bg-track">
                <div
                  className="h-1 rounded-full bg-brand transition-[width] duration-300"
                  style={{ width: `${update.status === 'downloading' ? update.progress * 100 : 100}%` }}
                />
              </div>
            </>
          ) : (
            <>
              {update.status === 'error' && update.error && (
                <span className="text-bad" title={update.error}>
                  {t('update.failed')}
                </span>
              )}
              <div className="flex gap-1.5">
                {update.supported ? (
                  <button
                    type="button"
                    onClick={install}
                    className="h-8 grow rounded-md bg-brand px-2 font-semibold text-on-brand hover:brightness-110"
                  >
                    {update.status === 'error' ? t('update.retry') : t('update.install')}
                  </button>
                ) : (
                  <button
                    type="button"
                    onClick={notes}
                    className="h-8 grow rounded-md bg-brand px-2 font-semibold text-on-brand hover:brightness-110"
                  >
                    {t('update.download')}
                  </button>
                )}
                {update.supported && update.page_url && (
                  <button
                    type="button"
                    onClick={notes}
                    className="h-8 rounded-md border border-edge px-2 text-soft hover:bg-raised"
                  >
                    {t('update.notes')}
                  </button>
                )}
              </div>
            </>
          )}
        </motion.div>
      )}
    </AnimatePresence>
  )
}
