"""ASCII logo / banner üretimi.

pyfiglet varsa 'Karabiber' logosunu üretir; yoksa sade bir metne düşer
(graceful degradation). CLI ve TUI aynı logoyu buradan alır.
"""
from __future__ import annotations

import sys

from . import __version__

_FALLBACK_LOGO = r"""
 _  __                _     _ _
| |/ /__ _ _ __ __ _| |__ (_) |__   ___ _ __
| ' // _` | '__/ _` | '_ \| | '_ \ / _ \ '__|
| . \ (_| | | | (_| | |_) | | |_) |  __/ |
|_|\_\__,_|_|  \__,_|_.__/|_|_.__/ \___|_|
""".strip("\n")

_TAGLINE = "modüler recon otomasyonu · yalnızca YETKİLİ hedefler 🌶️"


def ascii_logo() -> str:
    """'Karabiber' ASCII logosunu döndür (pyfiglet yoksa fallback)."""
    try:
        import pyfiglet

        return pyfiglet.figlet_format("Karabiber", font="slant").rstrip("\n")
    except Exception:  # pyfiglet yok ya da font bulunamadı
        return _FALLBACK_LOGO


def print_banner(stream=sys.stderr, color: bool = True) -> None:
    """Logoyu + sürüm/tagline satırını terminale bas.

    stdout'u (JSON/özet) kirletmemek için varsayılan stderr'e yazar. rich
    varsa renkli basar; yoksa düz metin kullanılır.
    """
    logo = ascii_logo()
    subtitle = f"v{__version__} — {_TAGLINE}"

    if color:
        try:
            from rich.console import Console

            console = Console(file=stream)
            console.print(logo, style="bold yellow", highlight=False)
            console.print(subtitle, style="dim")
            return
        except ImportError:  # rich yoksa düz metne düş
            pass

    print(logo, file=stream)
    print(subtitle, file=stream)
