#genai: WS-9 — Map technical exceptions to user-friendly error messages.
from __future__ import annotations


_ERROR_MAP = {
    "KeyError": "We couldn't read all the data from your document. The file format may be unsupported or the document structure is unusual.",
    "JSONDecodeError": "The document parsing returned unexpected results. Please try again or use a different file.",
    "ValueError": "Some values in the document couldn't be processed. Please check the file and try again.",
    "FileNotFoundError": "The file could not be found. Please re-upload it.",
    "ConnectError": "Could not connect to the server. Please try again in a moment.",
    "TimeoutException": "The operation took too long. Please try again with a smaller file.",
    "TimeoutError": "The operation took too long. Please try again with a smaller file.",
    "PermissionError": "Access denied. Please contact support.",
    "ApiError": "The server returned an error. Please try again in a moment.",
}

_FEATURE_HINTS = {
    "sister_quotation": "Make sure the file contains a quotation with items and prices.",
    "bill_to_make": "The file should be a DOC/DOCX with a table of items, quantities, and prices.",
    "gst_validate": "The file should be a GST invoice with line items.",
    "to_docx": "Make sure the file is a valid PDF or Excel file.",
    "to_pdf": "Make sure the file is a valid DOC, DOCX, or Excel file.",
    "bg_remove": "Make sure the image is clear and has a distinct foreground.",
    "watermark": "Make sure the image file is valid and not corrupted.",
    "catalog_pdf": "Make sure the image is clear and item details are correct.",
    "quotation_compare": "Each file should be a quotation document (DOC, DOCX, PDF, or Excel).",
}

# Codes referenced in the Error Code Catalogue (Section 19)
ERROR_CODES = {
    "E001": "We couldn't read the data from your document. The format may be unsupported.",
    "E002": "The AI couldn't understand this document. Please try a clearer file.",
    "E003": "The file appears to be corrupted or empty.",
    "E004": "Your monthly quota is exhausted ({used}/{limit}).",
    "E005": "Could not connect to the server. Please try again.",
    "E006": "The file is too large ({size} MB). Maximum is 15 MB.",
    "E007": "This file type is not supported.",
    "E008": "Processing took too long. Please try a smaller file.",
    "E009": "Something went wrong. Your file is still loaded — try another action.",
    "E010": "The format template could not be downloaded.",
}


def friendly_error(exc: Exception, feature: str = "") -> str:
    """Convert a Python exception to a user-friendly error message."""
    exc_type = type(exc).__name__
    base_msg = _ERROR_MAP.get(
        exc_type,
        "Something went wrong while processing your document.",
    )
    hint = _FEATURE_HINTS.get(feature, "")
    msg = f"❌ {base_msg}"
    if hint:
        msg += f"\n\n💡 *Tip:* {hint}"
    msg += "\n\nYour file is still loaded — you can try another action, or send /stop to start over."
    return msg
