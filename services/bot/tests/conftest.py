"""
#genai: Pytest fixtures shared across all DocSeva bot test modules.
"""
from __future__ import annotations

import json
import shutil
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ── Path helpers ──────────────────────────────────────────────────────────────

SAMPLES_DIR = Path(__file__).parent.parent.parent.parent / "test-samples"
QUOTATION_DIR = SAMPLES_DIR / "quotation"
INVOICE_DIR = SAMPLES_DIR / "invoice"
EXCEL_DIR = SAMPLES_DIR / "excel"
IMAGES_DIR = SAMPLES_DIR / "images"


def sample(rel: str) -> Path:
    """Return absolute path for a test-sample file."""
    return SAMPLES_DIR / rel


# ── Temp dir fixture ──────────────────────────────────────────────────────────

@pytest.fixture()
def tmp(tmp_path: Path) -> Path:
    """Isolated temp directory for a single test."""
    return tmp_path


# ── Company profile fixture ───────────────────────────────────────────────────

@pytest.fixture()
def company_profile() -> dict:
    return {
        "display_name": "Test Enterprises",
        "address": "123 Test Road, Mumbai, Maharashtra - 400001",
        "phone": "+91-99999-88888",
        "email": "test@example.com",
        "gstin": "27TESTCO001A1Z5",
        "bank_name": "State Bank of India",
        "bank_account": "12345678901",
        "bank_ifsc": "SBIN0000001",
    }


# ── Minimal parsed bill fixture ───────────────────────────────────────────────

@pytest.fixture()
def parsed_bill_complete() -> dict:
    return {
        "bill_to": {
            "name": "ABC Corp",
            "address": "100 Main Street, Delhi",
            "gstin": "07ABCDE1234F1Z5",
            "state_code": "07",
            "state_name": "Delhi",
        },
        "ship_to": {
            "name": "ABC Corp",
            "address": "100 Main Street, Delhi",
            "gstin": "07ABCDE1234F1Z5",
            "state_code": "07",
            "state_name": "Delhi",
        },
        "items": [
            {"sno": "1", "name": "Steel Pipes 2 inch", "hsn": "7304", "unit_cost": 1500.0, "amount": 15000.0},
            {"sno": "2", "name": "Elbow Fitting 2 inch", "hsn": "7307", "unit_cost": 250.0, "amount": 2500.0},
        ],
        "gst_rate": 18,
        "subtotal": 17500.0,
        "gst_amount": 3150.0,
        "total": 20650.0,
    }


@pytest.fixture()
def parsed_bill_no_hsn() -> dict:
    return {
        "bill_to": {
            "name": "XYZ Ltd",
            "address": "45 Park Ave, Mumbai",
            "gstin": "27XYZCO001B2Z6",
            "state_code": "27",
            "state_name": "Maharashtra",
        },
        "ship_to": {
            "name": "XYZ Ltd",
            "address": "45 Park Ave, Mumbai",
            "gstin": "27XYZCO001B2Z6",
            "state_code": "27",
            "state_name": "Maharashtra",
        },
        "items": [
            {"sno": "1", "name": "Water Pump 5HP", "hsn": "", "unit_cost": 42000.0, "amount": 42000.0},
            {"sno": "2", "name": "Pressure Gauge", "hsn": "", "unit_cost": 1800.0, "amount": 1800.0},
        ],
        "gst_rate": 18,
    }


@pytest.fixture()
def parsed_bill_no_billto() -> dict:
    return {
        "bill_to": {"name": "", "address": "", "gstin": "NA", "state_code": "", "state_name": ""},
        "ship_to": {"name": "", "address": "", "gstin": "NA", "state_code": "", "state_name": ""},
        "items": [
            {"sno": "1", "name": "Laptop Dell i5", "hsn": "8471", "unit_cost": 72000.0, "amount": 72000.0},
        ],
        "gst_rate": 18,
    }


# ── Mock OpenAI response ──────────────────────────────────────────────────────

def _make_openai_mock(content: str):
    """Return a mock that looks like openai.chat.completions.create response."""
    mock = MagicMock()
    mock.choices = [MagicMock()]
    mock.choices[0].message.content = content
    return mock


@pytest.fixture()
def mock_openai_bill(parsed_bill_complete):
    """Patch OpenAI to return a valid bill JSON."""
    with patch("openai.OpenAI") as mock_cls:
        instance = mock_cls.return_value
        instance.chat.completions.create.return_value = _make_openai_mock(
            json.dumps(parsed_bill_complete)
        )
        yield instance


# ── Telegram Update / Context mocks ──────────────────────────────────────────

@pytest.fixture()
def mock_update():
    update = MagicMock()
    update.effective_user.id = 123456789
    update.message = MagicMock()
    update.message.reply_text = AsyncMock()
    update.message.reply_document = AsyncMock()
    update.message.document = None
    update.callback_query = None
    return update


@pytest.fixture()
def mock_callback_query():
    query = MagicMock()
    query.answer = AsyncMock()
    query.edit_message_text = AsyncMock()
    query.edit_message_reply_markup = AsyncMock()
    query.message = MagicMock()
    query.message.reply_text = AsyncMock()
    query.message.reply_document = AsyncMock()
    return query


@pytest.fixture()
def mock_ctx():
    return MagicMock()
