#genai: Sprint 5 / WS-E — BSP package + factory.
from __future__ import annotations

from app.bsp.base import (
    BspError,
    BspProvider,
    InboundMedia,
    InboundMessage,
    OutboundButton,
    OutboundListItem,
    OutboundMessage,
)
from app.bsp.gupshup import GupshupBsp
from app.bsp.mock import MockBsp
from app.bsp.wati import WatiBsp
from app.config import get_settings


def build_bsp() -> BspProvider:
    """Factory keyed by settings.bsp_provider. Defaults to the in-memory mock."""
    s = get_settings()
    name = (s.bsp_provider or "mock").lower()
    if name == "wati":
        return WatiBsp(api_base=s.wati_api_base, token=s.wati_api_token)
    if name == "gupshup":
        return GupshupBsp(
            api_base=s.gupshup_api_base,
            api_key=s.gupshup_api_key,
            source=s.gupshup_source_number,
            app_name=s.gupshup_app_name,
        )
    return MockBsp()


__all__ = [
    "BspError",
    "BspProvider",
    "GupshupBsp",
    "InboundMedia",
    "InboundMessage",
    "MockBsp",
    "OutboundButton",
    "OutboundListItem",
    "OutboundMessage",
    "WatiBsp",
    "build_bsp",
]
