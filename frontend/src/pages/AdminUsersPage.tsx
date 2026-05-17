import { useState } from 'react'

import { Button, Card, Modal, TableFrame } from '../components/ui'
import {
  formatActivityDetail,
  formatActivityKind,
  type AdminUser,
  useAdminUserActivities,
  useAdminUsers,
} from '../lib/admin'
import { getErrorMessage } from '../lib/auth'

function formatDateTime(iso: string): string {
  return new Date(iso).toLocaleString()
}

export default function AdminUsersPage() {
  const users = useAdminUsers(true)
  const [selectedUser, setSelectedUser] = useState<AdminUser | null>(null)
  const activities = useAdminUserActivities(selectedUser?.id ?? null, selectedUser !== null)

  return (
    <>
      <header className="mb-4">
        <h1 className="text-2xl font-semibold tracking-tight">Users</h1>
        <p className="mt-1 text-sm text-zinc-400">
          Registered accounts and Telegram activity.
        </p>
      </header>

      <Card>
        <div className="mb-3 flex items-end justify-between">
          <div>
            <h2 className="text-lg font-semibold">All users</h2>
            <p className="text-sm text-zinc-400">
              Click a row to view activity history.
            </p>
          </div>
          {users.isFetching && (
            <span className="text-xs text-zinc-500">Refreshing…</span>
          )}
        </div>

        {users.isLoading ? (
          <p className="text-sm text-zinc-500">Loading users…</p>
        ) : users.error ? (
          <p className="text-sm text-red-600">
            Failed to load users: {getErrorMessage(users.error)}
          </p>
        ) : !users.data || users.data.length === 0 ? (
          <p className="text-sm text-zinc-500">No users yet.</p>
        ) : (
          <TableFrame>
            <table className="min-w-full divide-y divide-zinc-200 text-sm">
              <thead className="bg-zinc-100 text-xs uppercase tracking-wide text-zinc-400">
                <tr>
                  <th className="px-3 py-2 text-left font-medium">Email</th>
                  <th className="px-3 py-2 text-left font-medium">Display name</th>
                  <th className="px-3 py-2 text-left font-medium">Role</th>
                  <th className="px-3 py-2 text-left font-medium">Telegram</th>
                  <th className="px-3 py-2 text-right font-medium">Activities</th>
                  <th className="px-3 py-2 text-left font-medium">Joined</th>
                  <th className="px-3 py-2 text-right font-medium" aria-hidden />
                </tr>
              </thead>
              <tbody className="divide-y divide-zinc-100">
                {users.data.map((u) => (
                  <tr
                    key={u.id}
                    className="cursor-pointer hover:bg-zinc-50"
                    onClick={() => setSelectedUser(u)}
                  >
                    <td className="px-3 py-2 text-zinc-900">{u.email}</td>
                    <td className="px-3 py-2 text-zinc-700">
                      {u.display_name || <span className="text-zinc-600">—</span>}
                    </td>
                    <td className="px-3 py-2">
                      {u.is_admin ? (
                        <span className="rounded-full border border-indigo-500/40 bg-indigo-500/10 px-2 py-0.5 text-[10px] uppercase tracking-wide text-indigo-700">
                          admin
                        </span>
                      ) : (
                        <span className="text-xs text-zinc-500">user</span>
                      )}
                    </td>
                    <td className="px-3 py-2 text-zinc-700">
                      {u.telegram_connected ? (
                        u.telegram_username ? (
                          <span className="text-emerald-700">@{u.telegram_username}</span>
                        ) : (
                          <span className="text-emerald-700">Connected</span>
                        )
                      ) : (
                        <span className="text-zinc-500">—</span>
                      )}
                    </td>
                    <td className="px-3 py-2 text-right tabular-nums text-zinc-800">
                      {u.activity_count}
                    </td>
                    <td className="px-3 py-2 text-zinc-400">
                      {formatDateTime(u.created_at)}
                    </td>
                    <td className="px-3 py-2 text-right">
                      <Button
                        type="button"
                        variant="ghost"
                        className="px-2 py-1 text-xs"
                        onClick={(e) => {
                          e.stopPropagation()
                          setSelectedUser(u)
                        }}
                      >
                        View
                      </Button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </TableFrame>
        )}
      </Card>

      <Modal
        open={selectedUser !== null}
        onClose={() => setSelectedUser(null)}
        title={selectedUser ? `Activity · ${selectedUser.email}` : 'Activity'}
      >
        {selectedUser && (
          <div className="space-y-3 text-sm">
            <p className="text-zinc-500">
              {selectedUser.activity_count} recorded event
              {selectedUser.activity_count === 1 ? '' : 's'}
              {selectedUser.telegram_connected
                ? selectedUser.telegram_username
                  ? ` · Telegram @${selectedUser.telegram_username}`
                  : ' · Telegram connected'
                : ''}
            </p>

            {activities.isLoading ? (
              <p className="text-zinc-500">Loading activity…</p>
            ) : activities.error ? (
              <p className="text-red-600">
                Failed to load activity: {getErrorMessage(activities.error)}
              </p>
            ) : !activities.data || activities.data.length === 0 ? (
              <p className="text-zinc-500">No activity recorded yet.</p>
            ) : (
              <div className="max-h-[420px] overflow-y-auto rounded-lg border border-zinc-200">
                <table className="min-w-full divide-y divide-zinc-200 text-xs">
                  <thead className="sticky top-0 bg-zinc-100 text-[10px] uppercase tracking-wide text-zinc-400">
                    <tr>
                      <th className="px-2 py-2 text-left font-medium">When</th>
                      <th className="px-2 py-2 text-left font-medium">Type</th>
                      <th className="px-2 py-2 text-left font-medium">Detail</th>
                      <th className="px-2 py-2 text-left font-medium">Body</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-zinc-100 bg-white">
                    {activities.data.map((row) => (
                      <tr key={row.id}>
                        <td className="whitespace-nowrap px-2 py-2 text-zinc-500">
                          {formatDateTime(row.created_at)}
                        </td>
                        <td className="whitespace-nowrap px-2 py-2 text-zinc-800">
                          {formatActivityKind(row.kind)}
                        </td>
                        <td className="px-2 py-2 text-zinc-600">
                          {formatActivityDetail(row.detail)}
                        </td>
                        <td className="max-w-[200px] truncate px-2 py-2 text-zinc-700">
                          {row.body || '—'}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        )}
      </Modal>
    </>
  )
}
