import { useState } from 'react'

import { Button, Card, Input, Modal } from '../components/ui'
import { getErrorMessage, useMe } from '../lib/auth'
import {
  type Scraper,
  type ScraperPayload,
  useCreateScraper,
  useDeleteScraper,
  useScrapers,
  useUpdateScraper,
} from '../lib/scrapers'

const EMPTY_FORM: ScraperPayload = {
  name: '',
  bolha_enabled: true,
  avtonet_enabled: false,
}

function scraperToForm(scraper: Scraper): ScraperPayload {
  return {
    name: scraper.name,
    bolha_enabled: scraper.bolha_enabled,
    avtonet_enabled: scraper.avtonet_enabled,
  }
}

function SourceCheckboxes({
  bolha,
  onBolhaChange,
  disabled,
}: {
  bolha: boolean
  onBolhaChange: (checked: boolean) => void
  disabled?: boolean
}) {
  return (
    <fieldset className="space-y-2" disabled={disabled}>
      <legend className="mb-2 text-sm font-medium text-zinc-700">Sources</legend>
      <label className="flex cursor-pointer items-center gap-2 text-sm text-zinc-800">
        <input
          type="checkbox"
          checked={bolha}
          onChange={(e) => onBolhaChange(e.target.checked)}
          className="h-4 w-4 rounded border-zinc-300 text-indigo-600 focus:ring-indigo-500"
        />
        Bolha.com
      </label>
      <label className="flex items-center gap-2 text-sm text-zinc-400">
        <input
          type="checkbox"
          checked={false}
          disabled
          className="h-4 w-4 rounded border-zinc-200 text-zinc-300"
        />
        Avto.net
        <span className="text-xs">(coming soon)</span>
      </label>
    </fieldset>
  )
}

function ScraperForm({
  formKey,
  initial,
  submitLabel,
  onSubmit,
  onCancel,
  loading,
  error,
}: {
  formKey: string
  initial: ScraperPayload
  submitLabel: string
  onSubmit: (payload: ScraperPayload) => void
  onCancel: () => void
  loading: boolean
  error: string | null
}) {
  const [form, setForm] = useState(initial)

  return (
    <form
      key={formKey}
      className="space-y-4"
      onSubmit={(e) => {
        e.preventDefault()
        onSubmit({
          name: form.name.trim(),
          bolha_enabled: form.bolha_enabled,
          avtonet_enabled: false,
        })
      }}
    >
      <Input
        label="Name"
        value={form.name}
        onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
        placeholder="e.g. Daily Bolha cars"
        required
        maxLength={120}
        autoFocus
      />
      <SourceCheckboxes
        bolha={form.bolha_enabled}
        onBolhaChange={(checked) => setForm((f) => ({ ...f, bolha_enabled: checked }))}
        disabled={loading}
      />
      {error && <p className="text-sm text-red-600">{error}</p>}
      <div className="flex flex-wrap justify-end gap-2">
        <Button type="button" variant="ghost" onClick={onCancel} disabled={loading}>
          Cancel
        </Button>
        <Button type="submit" loading={loading}>
          {submitLabel}
        </Button>
      </div>
    </form>
  )
}

function formatSources(scraper: Scraper): string {
  const sources: string[] = []
  if (scraper.bolha_enabled) sources.push('Bolha.com')
  if (scraper.avtonet_enabled) sources.push('Avto.net')
  return sources.length > 0 ? sources.join(', ') : '—'
}

type EditorMode = { kind: 'create' } | { kind: 'edit'; scraper: Scraper }

export default function ScrapersPage() {
  const me = useMe()
  const scrapers = useScrapers(Boolean(me.data))
  const createScraper = useCreateScraper()
  const updateScraper = useUpdateScraper()
  const deleteScraper = useDeleteScraper()

  const [editor, setEditor] = useState<EditorMode | null>(null)
  const [deleteId, setDeleteId] = useState<string | null>(null)

  const createError = createScraper.error
    ? getErrorMessage(createScraper.error)
    : null
  const updateError = updateScraper.error
    ? getErrorMessage(updateScraper.error)
    : null

  const closeEditor = () => {
    setEditor(null)
    createScraper.reset()
    updateScraper.reset()
  }

  const handleCreate = async (payload: ScraperPayload) => {
    await createScraper.mutateAsync(payload)
    closeEditor()
  }

  const handleUpdate = async (id: string, payload: ScraperPayload) => {
    await updateScraper.mutateAsync({ id, ...payload })
    closeEditor()
  }

  const handleDelete = async (id: string) => {
    await deleteScraper.mutateAsync(id)
    setDeleteId(null)
    if (editor?.kind === 'edit' && editor.scraper.id === id) {
      closeEditor()
    }
  }

  const rows = scrapers.data ?? []

  return (
    <>
      <header className="mb-8 flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Scrapers</h1>
          <p className="mt-1 text-sm text-zinc-500">
            Configure named scrapers and which classifieds sites they use.
          </p>
        </div>
        <Button type="button" onClick={() => setEditor({ kind: 'create' })}>
          New scraper
        </Button>
      </header>

      <Card>
        {scrapers.isLoading ? (
          <p className="text-sm text-zinc-500">Loading scrapers…</p>
        ) : scrapers.error ? (
          <p className="text-sm text-red-600">Failed to load scrapers.</p>
        ) : rows.length === 0 ? (
          <p className="text-sm text-zinc-500">
            No scrapers yet. Create one to choose which sources to scrape.
          </p>
        ) : (
          <div className="overflow-x-auto rounded-lg border border-zinc-200">
            <table className="min-w-full divide-y divide-zinc-200 text-sm">
              <thead className="bg-zinc-100 text-xs uppercase tracking-wide text-zinc-400">
                <tr>
                  <th className="px-3 py-2 text-left font-medium">Name</th>
                  <th className="px-3 py-2 text-left font-medium">Sources</th>
                  <th className="px-3 py-2 text-left font-medium">Updated</th>
                  <th className="px-3 py-2 text-right font-medium">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-zinc-100">
                {rows.map((scraper) => {
                  const isDeleting = deleteId === scraper.id
                  return (
                    <tr key={scraper.id} className="hover:bg-zinc-50">
                      <td className="px-3 py-2.5 font-medium text-zinc-900">
                        {scraper.name}
                      </td>
                      <td className="px-3 py-2.5 text-zinc-600">
                        {formatSources(scraper)}
                      </td>
                      <td className="whitespace-nowrap px-3 py-2.5 text-zinc-500">
                        {new Date(scraper.updated_at).toLocaleString()}
                      </td>
                      <td className="px-3 py-2.5 text-right">
                        <div className="flex flex-wrap justify-end gap-1">
                          <Button
                            type="button"
                            variant="ghost"
                            className="px-2.5 py-1.5"
                            onClick={() => setEditor({ kind: 'edit', scraper })}
                          >
                            Edit
                          </Button>
                          {isDeleting ? (
                            <>
                              <Button
                                type="button"
                                variant="danger"
                                className="px-2.5 py-1.5"
                                loading={deleteScraper.isPending}
                                onClick={() => void handleDelete(scraper.id)}
                              >
                                Confirm
                              </Button>
                              <Button
                                type="button"
                                variant="ghost"
                                className="px-2.5 py-1.5"
                                disabled={deleteScraper.isPending}
                                onClick={() => setDeleteId(null)}
                              >
                                Cancel
                              </Button>
                            </>
                          ) : (
                            <Button
                              type="button"
                              variant="ghost"
                              className="px-2.5 py-1.5 text-red-600 hover:bg-red-50 hover:text-red-700"
                              onClick={() => setDeleteId(scraper.id)}
                            >
                              Delete
                            </Button>
                          )}
                        </div>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      <Modal
        open={editor?.kind === 'create'}
        onClose={closeEditor}
        title="New scraper"
      >
        <ScraperForm
          formKey="create"
          initial={EMPTY_FORM}
          submitLabel="Create"
          onSubmit={(payload) => void handleCreate(payload)}
          onCancel={closeEditor}
          loading={createScraper.isPending}
          error={createError}
        />
      </Modal>

      <Modal
        open={editor?.kind === 'edit'}
        onClose={closeEditor}
        title="Edit scraper"
      >
        {editor?.kind === 'edit' && (
          <ScraperForm
            formKey={editor.scraper.id}
            initial={scraperToForm(editor.scraper)}
            submitLabel="Save"
            onSubmit={(payload) => void handleUpdate(editor.scraper.id, payload)}
            onCancel={closeEditor}
            loading={updateScraper.isPending}
            error={updateError}
          />
        )}
      </Modal>
    </>
  )
}
