# DocSeva — Known Issues & Unhandled Scenarios

All 16 issues originally listed here have now been fixed. The full
release notes for each fix are below, followed by the (now empty) backlog
section so the file can be re-used for future findings.

---

## Status

| Priority | Total | Fixed | Remaining |
|----------|-------|-------|-----------|
| HIGH     | 5     | 5     | 0         |
| MEDIUM   | 6     | 6     | 0         |
| LOW      | 5     | 5     | 0         |
| **All**  | **16**| **16**| **0**     |

---

## Fix Notes

### KI-01: Logo asset for watermark / catalog (HIGH)
- Copied `test-samples/2.png` to `assets/logo.png` at the repo root.
- `services/bot/Dockerfile` already copies `assets/` into `/app/assets/`,
  so the logo is now baked into the image.
- `constants._resolve_logo` widened to scan more parent depths, so the
  logo also resolves correctly when running outside Docker (e.g. tests).
- Tests: `TestLogoAsset` in `tests/test_fixes.py`.

### KI-02: DOCX/XLSX → PDF resilience (HIGH)
- `app/processors/to_pdf.py` is pure-Python (fpdf2 + openpyxl/xlrd) — no
  LibreOffice required. Added `_pdf_para` resilience so an oversize token
  no longer crashes the converter.
- New `app/health.py` runs at startup and disables features whose
  dependencies are unavailable (PDF export, docxtpl, rembg).
- `_do_to_pdf` in `bot.py` now consults `get_health()` and reports a
  friendly error if PDF export is disabled.
- Tests: `tests/test_to_pdf.py`, `TestHealthCheck` in `tests/test_fixes.py`.

### KI-03: Sister quotation template engine (HIGH)
- `service.convert_with_template` now detects jinja-style placeholders
  (`{{ ... }}` / `{% ... %}`) in the uploaded template and renders it
  with `docxtpl` when present. Falls back to the built-in renderer when
  no placeholders are detected (or docxtpl fails).
- Added `docxtpl==0.19.1` to `requirements.txt`.
- Tests: `TestDocxtplTemplate` in `tests/test_fixes.py`.

### KI-04: Per-item GST rates with split summary (HIGH)
- LLM prompt now asks for a per-item `gst_rate`.
- New `_normalize_bill_data` recomputes `subtotal`, `gst_amount`,
  `total`, and a `gst_breakdown` array (`rate, taxable, tax`) on the
  server side — never trusts what the LLM returns.
- `generate_bill_pdf` accepts an optional `logo_path`, and `_draw_summary`
  renders a separate line per GST rate when multiple rates are present.
- Tests: `TestPerItemGstRate` in `tests/test_fixes.py`.

### KI-05: Price-adjust guard for non-quote outputs (HIGH)
- `service.adjust_prices` now iterates `quote.sections.items` correctly
  (previous code looked for a flat `quote.items` attribute that doesn't
  exist) and raises `ValueError` if the caller passes something other
  than a `QuoteDocument`.
- New `service.is_quote_document` helper; `bot._do_price_adjust` calls it
  before exposing the adjust step.
- Tests: `TestPriceAdjustGuard` in `tests/test_fixes.py`.

### KI-06: 15 MB upload limit (MEDIUM)
- `app/utils.is_file_size_ok` enforces `MAX_UPLOAD_BYTES = 15 MB`.
- `bot.handle_document` and `bot.handle_photo` check `doc.file_size` /
  `photo.file_size` before download and reject oversize files with a
  clear message.
- Tests: `TestFileSizeOk` in `tests/test_parsers.py`,
  `test_oversize_file_rejected` in `tests/test_bot_handlers.py`.

### KI-07: Custom comparison count (MEDIUM)
- `comparison_count_keyboard` now includes a "Custom (up to 10)" button.
- New `BotState.WAITING_COMPARISON_CUSTOM_COUNT` accepts a number 2–10
  and continues into the existing comparison flow.
- Tests: `TestComparisonCustomCount` in `tests/test_bot_handlers.py`.

### KI-08: Readable `/history` dates (MEDIUM)
- `app/utils.format_history_date` converts ISO 8601 timestamps to
  `31 May 2024` format and falls back gracefully on bad input.
- `cmd_history` in `bot.py` calls it for every row.
- Tests: `TestFormatHistoryDate` in `tests/test_parsers.py`.

### KI-09: Use uploaded company logo in Bill PDF (MEDIUM)
- New `_download_user_logo` helper downloads the user's logo from MinIO
  (using the `logo_key` already stored in `company_profile`) into a
  per-user tmp file.
- `_generate_bill_pdf` passes the logo path through to
  `bill_to_make.generate_bill_pdf`, which draws it in the header.
- Same helper is also used by the watermark feature (KI-13).
- Tests: `TestPerItemGstRate::test_pdf_generation_with_logo` in
  `tests/test_fixes.py`.

### KI-10: Chunked GST validation for long invoices (MEDIUM)
- `gst_validator.validate_gst_invoice` chunks input over 8000 chars
  via `app.utils.chunk_text` (paragraph-aware), validates each chunk in
  sequence, and merges results with deduplication + recomputed totals
  via the new `_merge_validation_results` helper.
- Tests: `TestGstChunkMerge` in `tests/test_fixes.py`.

### KI-11: Case/whitespace insensitive BillTo parsing (MEDIUM)
- New `app/utils.parse_billto_block` lowercases keys, collapses
  whitespace, and matches a wide alias map (`name`, `company`,
  `billto name`, `gst no`, `ship to name`, `delivery address`, …).
- `bot._do_bill_to_details` now uses it instead of an ad-hoc parser.
- Tests: `TestParseBillToBlock` in `tests/test_parsers.py`.

### KI-12: `.xls` and `.xlsx` extract_text (LOW)
- `extractors.extract_text` now handles `.xlsx` (openpyxl) and `.xls`
  (xlrd) — concatenates sheets with a `### Sheet: <name>` separator.
- Tests: `TestExtractTextExcel` in `tests/test_fixes.py`.

### KI-13: Image logo watermark with text fallback (LOW)
- `watermark.add_watermark` now accepts `mode` (`logo` | `text`),
  an optional `logo_path` override, and a `text` argument.
- New `watermark_mode_keyboard` in the bot offers both modes; if the
  user picks `text` the bot enters `WAITING_WATERMARK_TEXT` and stamps
  whatever they reply.
- A missing logo automatically falls back to a text watermark.
- Tests: `TestWatermarkModes` in `tests/test_fixes.py`,
  `TestWatermarkModeFlow` in `tests/test_bot_handlers.py`.

### KI-14: Styled comparison DOCX (LOW)
- `quotation_compare._build_docx` already produced a styled table
  (bold header, navy fill, alternating row shading, green/red price
  highlights). The KI-01 logo fix means the styled header logo now
  renders correctly in test/dev environments too. Also fixed a latent
  import bug (`CO_NAME` / `CO_ADDRESS` / `CO_PHONE`) by declaring
  defaults in `constants.py`.
- Tests: `TestComparisonStyling` in `tests/test_fixes.py`.

### KI-15: Per-user tmp file isolation (LOW)
- New `app/utils.user_tmp_path` builds
  `/tmp/docseva/<sanitised_uid>/<sanitised_filename>` and the `bot.py`
  wrapper `_user_tmp` is used by every per-user output path.
- File and user IDs are sanitised; `..` traversal is collapsed.
- Tests: `TestUserTmpPath` in `tests/test_parsers.py`.

### KI-16: Redis-backed session state (LOW)
- `SessionStore` now reads `REDIS_URL` at construction time. If Redis
  is reachable, sessions are persisted with a 7-day TTL and restored
  on the next message after a bot restart. Falls back transparently
  to in-memory only when Redis is unavailable.
- Added serialisation helpers (`_session_to_json` / `_session_from_json`)
  and new state values used by KI-07 and KI-13.
- Tests: `TestSessionStoreRedisFallback` in `tests/test_fixes.py`.

---

## Bonus Fixes Discovered Along the Way

| Issue | Fix |
|-------|-----|
| `bot.py` imported `pdf_to_docx` but only `convert_pdf_to_docx` existed | Added `pdf_to_docx` alias in `app/processors/pdf_to_docx.py` |
| `to_pdf._pdf_para` raised `FPDFException` on oversized tokens | Added X-reset + try/except with truncated fallback |
| `quotation_compare.py` imported `CO_NAME` from `constants` (didn't exist) | Declared `CO_NAME` / `CO_ADDRESS` / `CO_PHONE` / `CO_GSTIN` defaults |

---

## Test Suite Summary

```
================= 203 passed, 1 skipped, 43 warnings in 57.05s =================
```

- 203 tests passing, 1 environment-skip (docx watermark requires assets path).
- Overall coverage: **65%**.
- Per-module coverage (fix targets in **bold**):
  - `utils.py` — **98%**
  - `processors/constants.py` — **100%**
  - `processors/formats.py` — **100%**
  - `processors/gst_validator.py` — **96%**
  - `processors/watermark.py` — **97%**
  - `processors/bill_to_make.py` — **94%**
  - `processors/renderers.py` — **93%**
  - `processors/rename.py` — **90%**
  - `session_store.py` — **90%**
  - `processors/catalog_pdf.py` — 89%
  - `processors/to_pdf.py` — 87%
  - `processors/models.py` — 86%
  - `processors/quotation_compare.py` — 82%
  - `processors/excel_to_docx.py` — 76%
  - `health.py` — 74%
  - `processors/extractors.py` — 71%
  - `keyboards.py` — 67%
  - `api_client.py` — 64%
  - `processors/service.py` — 53%
  - `processors/llm_parser.py` — 95%
  - `processors/pdf_to_docx.py` — 39% (large table-rendering paths exercised only by real PDFs)
  - `bot.py` — 29% (most code paths require a real Telegram dispatcher; handler logic is still tested via mocks)
  - `handlers/onboarding.py` — 14%
  - `processors/bg_remove.py` — 0% (requires real rembg model)
  - `storage_client.py` — 0% (requires real MinIO)
  - `main.py` — 0% (entry point)

Lines uncovered overall: **1 101 of 3 181** — most are integration paths
that need a real Telegram update, real MinIO, or the rembg model and are
better exercised via the manual `TESTING_GUIDE.md` flows.

---

## Backlog

_(empty — add new findings here)_
