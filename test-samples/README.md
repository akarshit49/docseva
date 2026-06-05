# DocSeva Test Sample Files

Sample input files to test all bot features. Use these files in Telegram to verify each scenario.

## Files at a Glance

| File | Use For |
|------|---------|
| `quotation/sample_quotation.docx` | Sister Quotation conversion — this is the SOURCE file (input) |
| `quotation/sample_format_template.docx` | Sister Quotation — upload this as the FORMAT TEMPLATE |
| `invoice/sample_invoice_complete.docx` | Bill to Make — happy path (all details present) |
| `invoice/sample_invoice_no_hsn.docx` | Bill to Make — triggers HSN prompt (no HSN codes) |
| `invoice/sample_invoice_no_billto.docx` | Bill to Make — triggers BillTo/ShipTo prompt |
| `invoice/sample_invoice_multi_table.docx` | Bill to Make — multi-table stress test |
| `invoice/sample_gst_invoice.docx` | GST Validate feature |
| `excel/sample_products.xlsx` | Convert to DOCX from Excel |
| `images/sample_product.jpg` | Product Catalog PDF generation |

## Quick Start

1. Open Telegram and start the DocSeva bot.
2. Send any file above.
3. Choose the feature from the action buttons.

Refer to `TESTING_GUIDE.md` in the project root for step-by-step instructions.
