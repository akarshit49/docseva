//genai: Catalog client wrapper — collects item title, price, description and
//        posts to /process/catalog. The PDF result auto-incorporates the user's
//        company profile (name, address, GSTIN, phone) and uploaded logo.
'use client'

import * as React from 'react'

import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { ProcessRunner } from '@/components/quote/process-runner'
import { cn } from '@/lib/utils'

export function CatalogForm() {
  const [itemName, setItemName] = React.useState('')
  const [price, setPrice] = React.useState('')
  const [description, setDescription] = React.useState('')

  const params: Record<string, unknown> = {
    item_name: itemName.trim(),
  }
  if (price.trim()) params.price = price.trim()
  if (description.trim()) params.description = description.trim()

  const submitDisabled = !itemName.trim()

  return (
    <ProcessRunner
      feature="catalog"
      title="Create a catalog page"
      description="Drop a product photo, fill in the details, get a single-page branded PDF."
      accept={['.png', '.jpg', '.jpeg', '.webp']}
      hint="Product image — PNG, JPG, or WEBP. ≤ 15 MB."
      submitLabel={submitDisabled ? 'Add item name first' : 'Generate catalog'}
      params={params}
      extra={
        <div className="space-y-4">
          <div className="space-y-1.5">
            <Label htmlFor="cat_item">
              Item name <span className="text-danger">*</span>
            </Label>
            <Input
              id="cat_item"
              value={itemName}
              onChange={(e) => setItemName(e.target.value.slice(0, 80))}
              placeholder="D16 3D Lean HST 2010"
              maxLength={80}
            />
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="cat_price">
              Price{' '}
              <span className="text-xs text-ink-400">(optional)</span>
            </Label>
            <Input
              id="cat_price"
              value={price}
              onChange={(e) => setPrice(e.target.value.slice(0, 40))}
              placeholder='e.g. "Rs. 2,24,000" or "On request"'
              maxLength={40}
            />
            <p className="text-xs text-ink-500">
              Free-form text — include the currency symbol you want printed.
            </p>
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="cat_desc">
              Description{' '}
              <span className="text-xs text-ink-400">(optional)</span>
            </Label>
            <textarea
              id="cat_desc"
              value={description}
              onChange={(e) => setDescription(e.target.value.slice(0, 800))}
              placeholder="Compact, precision-engineered 3D lean instrument with..."
              rows={4}
              maxLength={800}
              className={cn(
                'w-full rounded-lg border border-ink-300 bg-white px-3 py-2 text-sm text-ink-900',
                'placeholder:text-ink-500 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand',
              )}
            />
            <p className="text-xs text-ink-500">
              Up to 800 characters. Longer descriptions are truncated to fit the page.
            </p>
          </div>
        </div>
      }
    />
  )
}
