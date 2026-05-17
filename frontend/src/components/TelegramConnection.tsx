import { useState } from 'react'

import {
  useTelegramDisconnect,
  useTelegramLink,
  useTelegramStatus,
  useTelegramTest,
} from '../lib/telegram'
import { Button, Modal } from './ui'

function TelegramIcon() {
  return (
    <svg className="h-5 w-5" viewBox="0 0 24 24" fill="currentColor" aria-hidden>
      <path d="M11.944 0A12 12 0 0 0 0 12a12 12 0 0 0 12 12 12 12 0 0 0 12-12A12 12 0 0 0 12 0a12 12 0 0 0-.056 0zm4.962 7.224c.1-.002.321.023.465.14a.506.506 0 0 1 .171.325c.016.093.036.306.02.472-.18 1.898-.962 6.502-1.36 8.627-.168.9-.499 1.201-.82 1.23-.696.065-1.225-.46-1.9-.902-1.056-.693-1.653-1.124-2.678-1.8-1.185-.78-.417-1.21.258-1.91.177-.184 3.247-2.977 3.307-3.23.007-.032.014-.15-.056-.212s-.174-.041-.249-.024c-.106.024-1.793 1.14-5.061 3.345-.48.33-.913.49-1.302.48-.428-.008-1.252-.241-1.865-.44-.752-.245-1.349-.374-1.297-.789.027-.216.325-.437.893-.663 3.498-1.524 5.83-2.529 6.998-3.014 3.332-1.386 4.025-1.627 4.476-1.635z" />
    </svg>
  )
}

export function TelegramConnection() {
  const [modalOpen, setModalOpen] = useState(false)
  const [waiting, setWaiting] = useState(false)
  const [deepLink, setDeepLink] = useState<string | null>(null)
  const [linkError, setLinkError] = useState<string | null>(null)
  const [testSent, setTestSent] = useState(false)

  const status = useTelegramStatus(true, waiting && modalOpen ? 2000 : false)
  const link = useTelegramLink()
  const disconnect = useTelegramDisconnect()
  const test = useTelegramTest()

  const connected = status.data?.connected ?? false
  const username = status.data?.username
  const dialogOpen = modalOpen && !connected
  const awaitingLink = waiting && modalOpen && !connected

  const handleConnect = async () => {
    setLinkError(null)
    setModalOpen(true)
    try {
      const result = await link.mutateAsync()
      setDeepLink(result.deep_link_url)
      setWaiting(true)
    } catch {
      setLinkError('Could not start Telegram linking. Is Telegram configured on the server?')
      setWaiting(false)
    }
  }

  const handleOpenTelegram = () => {
    if (deepLink) {
      window.open(deepLink, '_blank', 'noopener,noreferrer')
    }
  }

  const handleDisconnect = async () => {
    await disconnect.mutateAsync()
    setTestSent(false)
  }

  const handleTest = async () => {
    setTestSent(false)
    try {
      await test.mutateAsync()
      setTestSent(true)
    } catch {
      setTestSent(false)
    }
  }

  return (
    <>
      <ul className="mt-4 space-y-3">
        <li className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-zinc-200 bg-zinc-50/80 px-4 py-3">
          <div className="flex min-w-0 items-center gap-3">
            <span
              className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-sky-100 text-sky-700"
              aria-hidden
            >
              <TelegramIcon />
            </span>
            <div>
              <p className="font-medium text-zinc-900">Telegram</p>
              <p className="text-sm text-zinc-500">
                {connected
                  ? username
                    ? `Connected as @${username}`
                    : 'Connected — alerts enabled for new matches'
                  : 'Push alerts for new matches as they are found.'}
              </p>
              {connected && status.data && !status.data.notifications_enabled && (
                <p className="mt-1 text-xs text-amber-700">Notifications paused in Telegram</p>
              )}
              {testSent && (
                <p className="mt-1 text-xs text-emerald-700">Test message sent</p>
              )}
            </div>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            {status.isLoading ? (
              <span className="text-xs text-zinc-500">Loading…</span>
            ) : connected ? (
              <>
                <span className="inline-flex items-center gap-1.5 rounded-full bg-emerald-50 px-2.5 py-0.5 text-xs font-medium text-emerald-800">
                  <span className="h-1.5 w-1.5 rounded-full bg-emerald-500" aria-hidden />
                  Connected
                </span>
                <Button
                  type="button"
                  variant="ghost"
                  className="px-3 py-1.5"
                  loading={test.isPending}
                  onClick={() => void handleTest()}
                >
                  Send test
                </Button>
                <Button
                  type="button"
                  variant="ghost"
                  className="px-3 py-1.5"
                  loading={disconnect.isPending}
                  onClick={() => void handleDisconnect()}
                >
                  Disconnect
                </Button>
              </>
            ) : (
              <Button
                type="button"
                variant="primary"
                className="px-3 py-1.5"
                loading={link.isPending}
                onClick={() => void handleConnect()}
              >
                Connect
              </Button>
            )}
          </div>
        </li>
      </ul>

      <Modal
        open={dialogOpen}
        onClose={() => {
          setModalOpen(false)
          setWaiting(false)
          setDeepLink(null)
          setLinkError(null)
        }}
        title="Connect Telegram"
      >
        <div className="space-y-4 text-sm text-zinc-600">
          <p>
            Open Telegram and tap <strong className="text-zinc-900">Start</strong> on the Spider
            bot. We will link this chat to your account.
          </p>

          {linkError && <p className="text-red-600">{linkError}</p>}

          {deepLink && (
            <div className="space-y-3">
              <Button type="button" className="w-full" onClick={handleOpenTelegram}>
                Open Telegram
              </Button>
              {awaitingLink && (
                <p className="text-center text-xs text-zinc-500">
                  Waiting for connection…
                </p>
              )}
            </div>
          )}

          {link.isPending && !deepLink && !linkError && (
            <p className="text-center text-zinc-500">Preparing link…</p>
          )}
        </div>
      </Modal>
    </>
  )
}
