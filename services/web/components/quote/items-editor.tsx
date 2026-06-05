//genai: Sprint 3 / WS-H — editable table for the confirmation step.
'use client'

import * as React from 'react'
import { Plus, Trash2 } from 'lucide-react'

import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { formatRupees } from '@/lib/utils'
import type { QuoteItemPreview, QuotePreview, QuoteSectionPreview } from '@/lib/types'

export interface ItemsEditorProps {
  preview: QuotePreview
  onChange: (next: QuotePreview) => void
}

export function ItemsEditor({ preview, onChange }: ItemsEditorProps) {
  // We flatten sections to a single editable list; on save we put everything
  // back under one "GENERAL" section. Multi-section quotes are rare for the
  // dealer use-case and the simpler UX is worth the trade-off.
  const flatItems: QuoteItemPreview[] = React.useMemo(
    () => preview.sections.flatMap((s) => s.items),
    [preview],
  )

  const updateRecipient = (field: keyof QuotePreview, value: string | string[]) => {
    onChange({ ...preview, [field]: value })
  }

  const updateItems = (next: QuoteItemPreview[]) => {
    const section: QuoteSectionPreview = {
      name: preview.sections[0]?.name || 'GENERAL',
      items: next,
    }
    onChange({ ...preview, sections: [section], subtotal: subtotalOf(next) })
  }

  const editItem = (idx: number, patch: Partial<QuoteItemPreview>) => {
    const next = flatItems.map((it, i) => {
      if (i !== idx) return it
      const merged = { ...it, ...patch }
      const qty = Number.parseFloat(String(merged.qty).replace(/[^\d.]/g, '')) || 0
      merged.total = Math.round(qty * (merged.unit_price || 0) * 100) / 100
      return merged
    })
    updateItems(next)
  }

  const deleteItem = (idx: number) => {
    updateItems(flatItems.filter((_, i) => i !== idx))
  }

  const addItem = () => {
    updateItems([
      ...flatItems,
      {
        sno: `${flatItems.length + 1}.`,
        description: '',
        qty: '1',
        unit_price: 0,
        total: 0,
      },
    ])
  }

  const missingHsn = flatItems.filter((it) => !lookupHsn(it)).length

  return (
    <div className="space-y-6">
      <fieldset className="rounded-xl border border-ink-100 p-4">
        <legend className="px-2 text-sm font-medium text-ink-900">Customer (Bill To)</legend>
        <div className="grid gap-3 sm:grid-cols-2">
          <div className="space-y-1.5">
            <Label htmlFor="recipient_name">Name</Label>
            <Input
              id="recipient_name"
              value={preview.recipient_name || ''}
              onChange={(e) => updateRecipient('recipient_name', e.target.value)}
            />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="recipient_subject">Subject</Label>
            <Input
              id="recipient_subject"
              value={preview.subject || ''}
              onChange={(e) => updateRecipient('subject', e.target.value)}
            />
          </div>
          <div className="space-y-1.5 sm:col-span-2">
            <Label htmlFor="recipient_address">Address</Label>
            <Input
              id="recipient_address"
              value={(preview.recipient_address_lines || []).join(', ')}
              onChange={(e) =>
                updateRecipient(
                  'recipient_address_lines',
                  e.target.value
                    .split(',')
                    .map((s) => s.trim())
                    .filter(Boolean),
                )
              }
            />
          </div>
        </div>
      </fieldset>

      <fieldset className="rounded-xl border border-ink-100">
        <legend className="ml-4 px-2 text-sm font-medium text-ink-900">Items</legend>
        <div className="overflow-x-auto px-2 pb-4">
          <table className="w-full text-sm">
            <thead className="text-left text-xs uppercase text-ink-500">
              <tr>
                <th className="w-10 px-2 py-2">#</th>
                <th className="px-2 py-2">Description</th>
                <th className="w-20 px-2 py-2">Qty</th>
                <th className="w-32 px-2 py-2">Unit ₹</th>
                <th className="w-32 px-2 py-2 text-right">Total</th>
                <th className="w-10 px-2 py-2"></th>
              </tr>
            </thead>
            <tbody>
              {flatItems.map((it, idx) => (
                <tr key={idx} className="border-t border-ink-100 align-top">
                  <td className="px-2 py-2 text-ink-500">{idx + 1}</td>
                  <td className="px-2 py-2">
                    <Input
                      value={it.description}
                      onChange={(e) => editItem(idx, { description: e.target.value })}
                      placeholder="Item description"
                    />
                  </td>
                  <td className="px-2 py-2">
                    <Input
                      value={it.qty}
                      onChange={(e) => editItem(idx, { qty: e.target.value })}
                    />
                  </td>
                  <td className="px-2 py-2">
                    <Input
                      type="number"
                      step="0.01"
                      value={it.unit_price || 0}
                      onChange={(e) =>
                        editItem(idx, { unit_price: Number(e.target.value) || 0 })
                      }
                    />
                  </td>
                  <td className="px-2 py-2 text-right text-ink-700">
                    {formatRupees(it.total)}
                  </td>
                  <td className="px-2 py-2">
                    <button
                      type="button"
                      onClick={() => deleteItem(idx)}
                      aria-label={`Remove item ${idx + 1}`}
                      className="rounded p-1 text-ink-500 hover:bg-danger-soft hover:text-danger"
                    >
                      <Trash2 className="h-4 w-4" aria-hidden />
                    </button>
                  </td>
                </tr>
              ))}
              {flatItems.length === 0 ? (
                <tr>
                  <td colSpan={6} className="px-2 py-6 text-center text-sm text-ink-500">
                    No items yet. Add one manually.
                  </td>
                </tr>
              ) : null}
            </tbody>
            <tfoot>
              <tr className="border-t border-ink-100">
                <td colSpan={4} className="px-2 py-3 text-right text-sm font-medium text-ink-700">
                  Subtotal
                </td>
                <td className="px-2 py-3 text-right text-base font-semibold text-ink-900">
                  {formatRupees(subtotalOf(flatItems))}
                </td>
                <td />
              </tr>
            </tfoot>
          </table>
        </div>
        <div className="flex items-center justify-between border-t border-ink-100 px-4 py-3">
          <Button variant="outline" size="sm" onClick={addItem}>
            <Plus className="h-4 w-4" aria-hidden /> Add item
          </Button>
          {missingHsn > 0 ? (
            <p className="text-xs text-warning">
              {missingHsn} item{missingHsn === 1 ? '' : 's'} missing HSN — fine for quotes,
              required if you later convert to invoice.
            </p>
          ) : null}
        </div>
      </fieldset>
    </div>
  )
}

function subtotalOf(items: QuoteItemPreview[]): number {
  return items.reduce((sum, it) => sum + (it.total || 0), 0)
}

function lookupHsn(_item: QuoteItemPreview): string | undefined {
  // HSN is not currently part of QuoteItemPreview but the renderer captures it
  // on the server side. Treat absence as "missing" for the warning chip.
  return undefined
}
