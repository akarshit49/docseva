# DocSeva Bot — Manual Testing Guide

This guide walks you through testing every feature of the DocSeva bot in Telegram.
No technical knowledge needed — just follow the steps.

> **Sample files** are in the `test-samples/` folder in this project.
> Copy them to your phone or desktop before starting.

---

## Before You Start

1. Open Telegram and find your DocSeva bot.
2. Type `/start` — complete the registration if you haven't already.
3. Type `/menu` — you should see the main menu with your plan info.

---

## Feature 1 — Sister Quotation

**What it does:** Converts a quotation document into another company's format style.

### Step A: Save a Format Template

1. Send the file `test-samples/quotation/sample_format_template.docx` to the bot.
2. Tap **Sister Quotation** button.
3. If no templates saved yet, bot says "No Format Templates Saved Yet" and asks you to upload one — this is correct.
4. Send `sample_format_template.docx` again when it asks.
5. Bot asks: "Enter a name for this format."
6. Type any name, e.g. `My Format`.
7. ✅ Bot replies: "Format saved! (1/10)"

### Step B: Convert a Quotation

1. Send the file `test-samples/quotation/sample_quotation.docx`.
2. Tap **Sister Quotation**.
3. You see a list of saved formats — tap `My Format`.
4. ✅ Bot processes and sends back a converted `.docx` file.

### Step C: Manage Templates

1. Type `/formats`.
2. You see your saved formats with a Delete button.
3. Tap Delete next to a format.
4. ✅ Bot confirms deletion.

### Expected Failures (Bot Should Handle Gracefully)

- Send a `.jpg` image when asked for a template → bot says "Please send PDF/DOC/DOCX".
- Have no templates saved → bot asks you to upload one before converting.
- Send wrong format file → bot shows an error and resets.

---

## Feature 2 — Bill to Make

**What it does:** Reads a purchase order / supply list and generates a professional GST invoice PDF.

### Test Case 1: Happy Path (All Details Present)

1. Send `test-samples/invoice/sample_invoice_complete.docx`.
2. Tap **Bill to Make**.
3. Bot asks: "Send bill number and date."
4. Type: `INV-001, 31-05-2024`
5. ✅ Bot parses the document and generates a PDF invoice — check that all items, HSN codes, and totals appear correctly.

### Test Case 2: Missing HSN Codes

1. Send `test-samples/invoice/sample_invoice_no_hsn.docx`.
2. Tap **Bill to Make** → enter `INV-002, 31-05-2024`.
3. ✅ Bot asks: "These items are missing HSN codes: 1. Water Pump… Please provide codes."
4. Type the codes, e.g.:
   ```
   1: 8413
   2: 9026
   3: 8536
   4: 8481
   5: 8544
   ```
5. ✅ Bot accepts all and generates the PDF.

### Test Case 3: Partial HSN Codes (Re-prompt)

1. Same as Test Case 2.
2. When bot asks for HSN codes, only type `1: 8413` (only item 1).
3. ✅ Bot should say "2 items still missing" and ask again for the remaining items.
4. Provide the rest — bot proceeds.

### Test Case 4: Missing BillTo/ShipTo

1. Send `test-samples/invoice/sample_invoice_no_billto.docx`.
2. Tap **Bill to Make** → enter `INV-003, 31-05-2024`.
3. ✅ Bot asks: "The document doesn't contain billing address details. Please provide them."
4. Type:
   ```
   Name: ABC Technologies Ltd
   Address: 45 Sector 5, Noida, UP - 201301
   GSTIN: 09ABCDE1234F1Z5
   State: Uttar Pradesh
   ```
5. ✅ Bot generates the PDF with your provided details.

### Test Case 5: Multi-Table Document

1. Send `test-samples/invoice/sample_invoice_multi_table.docx`.
2. Tap **Bill to Make** → enter bill number and date.
3. ✅ Bot should number items sequentially (1, 2, 3, 4, 5, 6...) across both tables — not restart at 1.

### Test Case 6: Invalid Date Input

1. Send any invoice file → tap **Bill to Make**.
2. When asked for bill number and date, type: `INV-001, 3454`
3. ✅ Bot should say "That is not a valid date" and ask again.
4. Try again: `INV-001, 31-05-2024` — this should work.

---

## Feature 3 — GST Validate

**What it does:** Checks a GST invoice for errors — GSTIN format, HSN codes, tax calculations.

1. Send `test-samples/invoice/sample_gst_invoice.docx`.
2. Tap **GST Validate**.
3. ✅ Bot analyses and sends back a detailed validation report showing ✅ or ❌ for each field.

---

## Feature 4 — Convert to DOCX

**What it does:** Converts an Excel spreadsheet to a Word document.

1. Send `test-samples/excel/sample_products.xlsx`.
2. Tap **Convert to DOCX**.
3. ✅ Bot sends back a `.docx` file with the Excel data in a table.

---

## Feature 5 — Convert to PDF

**What it does:** Converts a Word document to PDF.

1. Send `test-samples/quotation/sample_quotation.docx`.
2. Tap **Convert to PDF**.
3. ✅ Bot sends back a `.pdf` file.

---

## Feature 6 — Rename File

**What it does:** Renames a file without changing its content.

1. Send any file (e.g., `sample_quotation.docx`).
2. Tap **Rename**.
3. Bot asks: "Enter the new filename (without extension)."
4. Type: `My Company Quotation June 2024`
5. ✅ Bot sends back `My Company Quotation June 2024.docx`.

---

## Feature 7 — Watermark

**What it does:** Adds a "CONFIDENTIAL" or company watermark to a document/image.

1. Send `test-samples/images/sample_product.jpg`.
2. Tap **Watermark**.
3. ✅ Bot sends back the image with a watermark applied.

---

## Feature 8 — Background Remove

**What it does:** Removes the background from a product image (leaves just the product).

1. Send `test-samples/images/sample_product.jpg`.
2. Tap **Remove Background**.
3. ✅ Bot sends back a `.png` image with the background removed.

> Note: This can take 15–30 seconds. The bot shows "Removing background…" — just wait.

---

## Feature 9 — Product Catalog PDF

**What it does:** Creates a one-page product catalog PDF from an image.

1. Send `test-samples/images/sample_product.jpg`.
2. Tap **Product Catalog**.
3. Bot asks: "Enter item details in format: `Item Name | Description | Price`"
4. Type: `Industrial Gear Pump 5HP | Flow Rate: 500 LPH, Head: 30m | ₹42,000`
5. ✅ Bot sends back a professional catalog PDF.

---

## Feature 10 — Quotation Comparison

**What it does:** Compares multiple quotations side by side in a table.

1. Send `test-samples/quotation/sample_quotation.docx`.
2. Tap **Compare Quotations**.
3. Bot asks how many quotations — tap **2**.
4. Send a second quotation file (you can send `sample_quotation.docx` again).
5. ✅ Bot sends back a DOCX table comparing all quotations.

---

## Navigation & Session Tests

### Exit / New File buttons

- At any point tap **Exit** → ✅ Bot shows the main menu (not just "session ended").
- At any point tap **New File** → ✅ Bot says "Ready for a new file!" and accepts the next upload.

### /stop command

- Type `/stop` at any time → ✅ Bot resets your session cleanly.

### /settings — Company Profile

1. Type `/settings`.
2. Tap **Company Name** → type your company name → ✅ Updated.
3. Tap **GSTIN** → type your GSTIN → ✅ Updated.
4. The company name and GSTIN should appear on all generated invoices and catalogs.

---

## Error Scenarios (Bot Must NOT Crash)

| Scenario | What to do | Expected Result |
|----------|------------|-----------------|
| Send unsupported file | Send a `.zip` or `.exe` file | Bot says "Unsupported file type" |
| Send empty message | Just press send with no text | Bot says "Please send a file…" |
| Send wrong format when bot expects a number | Type `abc` when bot asks for date | Bot re-prompts with correct format example |
| API connection issue | (simulate by disconnecting Wi-Fi briefly) | Bot replies "Something went wrong" — does NOT crash |
| Tap a button twice quickly | Double-tap any inline button | No duplicate actions — bot handles gracefully |

---

## How to Run Automated Tests

```bash
cd /Users/Akarshit.jain/Desktop/DocSeva
docker run --rm \
  -v "$(pwd)/services/bot:/app" \
  -v "$(pwd)/test-samples:/test-samples" \
  -w /app \
  -e OPENAI_API_KEY=fake -e TELEGRAM_BOT_TOKEN=1234567890:fake \
  -e API_BASE_URL=http://api:8000 -e API_BOT_TOKEN=faketoken \
  -e MINIO_ENDPOINT=minio:9000 -e MINIO_ACCESS_KEY=fakekey \
  -e MINIO_SECRET_KEY=fakesecret -e MINIO_BUCKET_ASSETS=assets \
  -e MINIO_BUCKET_OUTPUTS=outputs -e REDIS_URL=redis://redis:6379/0 \
  docseva-bot \
  sh -c "pip install pytest pytest-asyncio -q && python -m pytest tests/ -v"
```

Current results: **113 passed, 3 skipped** (skipped = require company logo asset not available in test environment).
