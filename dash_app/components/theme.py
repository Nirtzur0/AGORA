from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Theme:
    brand: str = "#0b5d5d"
    brand_alt: str = "#1f7a8c"
    surface: str = "#f5f7f8"
    text: str = "#1e2933"
    success: str = "#1b6e3c"
    warning: str = "#b45309"
    danger: str = "#b91c1c"


THEME = Theme()


def status_color(status: str) -> str:
    normalized = (status or "").lower()
    if normalized == "pass":
        return THEME.success
    if normalized in {"warn", "warning"}:
        return THEME.warning
    return THEME.danger
