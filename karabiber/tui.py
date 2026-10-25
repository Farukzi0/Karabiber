"""Textual tabanlı TUI.

Üstte pyfiglet ASCII logo, solda canlı tarama logu, sağda AI yorum paneli.
Tarama bir worker thread'de çalışır; log satırları thread-güvenli şekilde
UI'ye post edilir.
"""
from __future__ import annotations

from typing import Any

from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Footer, Header, RichLog, Static

from .banner import ascii_logo
from .config import Config
from .core import ReconEngine

_LOGO = ascii_logo()


class KarabiberApp(App):
    CSS = """
    #logo { height: auto; color: $warning; content-align: center top; }
    #banner { height: auto; color: $text-muted; }
    #body { height: 1fr; }
    #log { width: 2fr; border: round $primary; }
    #ai  { width: 1fr; border: round $warning; }
    .title { text-style: bold; }
    """
    BINDINGS = [("q", "quit", "Çıkış")]

    def __init__(
        self,
        config: Config,
        target: str,
        profile: str,
        use_llm: bool,
        output_path: str | None,
    ) -> None:
        super().__init__()
        self.config = config
        self.target = target
        self.profile = profile
        self.use_llm = use_llm
        self.output_path = output_path
        self.report: dict[str, Any] | None = None

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield Static(_LOGO, id="logo")
        yield Static(
            "Yalnızca YETKİLİ hedefler için — eğitim/CTF. "
            f"Hedef: {self.target} | Profil: {self.profile}",
            id="banner",
        )
        with Horizontal(id="body"):
            with Vertical(id="log"):
                yield Static("Tarama Logu", classes="title")
                yield RichLog(id="logview", highlight=True, markup=True, wrap=True)
            with Vertical(id="ai"):
                yield Static("AI Yorumu (ÖNERİ)", classes="title")
                yield RichLog(id="aiview", markup=True, wrap=True)
        yield Footer()

    def on_mount(self) -> None:
        self._log("[dim]Tarama başlatılıyor…[/dim]")
        # Worker: thread'de çalıştır (subprocess/requests blocking olduğu için)
        self.run_scan()

    # -- Worker ---------------------------------------------------------- #
    def run_scan(self) -> None:
        from textual.worker import Worker  # noqa: F401

        self.run_worker(self._scan_worker, thread=True, name="recon")

    def _scan_worker(self) -> None:
        def progress(event: str, message: str) -> None:
            # UI thread'ine güvenli post
            if event == "ai":
                self.call_from_thread(self._ai, message)
            else:
                self.call_from_thread(self._log, self._fmt(event, message))

        engine = ReconEngine(
            self.config,
            profile=self.profile,
            use_llm=self.use_llm,
            progress=progress,
        )
        report = engine.run(self.target)
        self.report = report
        self.call_from_thread(self._finish, report)

    # -- UI yardımcıları ------------------------------------------------- #
    def _fmt(self, event: str, message: str) -> str:
        colors = {
            "start": "bold cyan",
            "module_start": "cyan",
            "module_end": "green",
            "note": "white",
            "done": "bold green",
            "error": "red",
        }
        style = colors.get(event, "white")
        return f"[{style}]{message}[/{style}]"

    def _log(self, text: str) -> None:
        self.query_one("#logview", RichLog).write(text)

    def _ai(self, text: str) -> None:
        self.query_one("#aiview", RichLog).write(text)

    def _finish(self, report: dict[str, Any]) -> None:
        ai = report.get("ai", {})
        if ai.get("status") == "ok" and ai.get("suggestion"):
            self._ai("")
            self._ai("[yellow]" + ai["suggestion"] + "[/yellow]")
            self._ai("\n[dim]— AI çıktısı doğrulanmamış ÖNERİ'dir.[/dim]")
        else:
            self._ai(f"[dim]AI paneli atlandı ({ai.get('status')}).[/dim]")

        if self.output_path:
            from .reporter import write_json

            write_json(report, self.output_path)
            self._log(f"[green]JSON rapor yazıldı: {self.output_path}[/green]")
        self._log("[bold green]Bitti. Çıkış için 'q'.[/bold green]")


def run_tui(config, target, profile, use_llm, output_path) -> dict[str, Any] | None:
    app = KarabiberApp(config, target, profile, use_llm, output_path)
    app.run()
    return app.report
