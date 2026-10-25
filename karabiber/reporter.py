"""Raporlayıcı: JSON + okunabilir terminal özeti.

rich varsa renkli tablo basar; yoksa düz metne düşer (graceful).
"""
from __future__ import annotations

import datetime as _dt
import json
from typing import Any

try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table

    _RICH = True
except ImportError:  # rich zorunlu değil
    _RICH = False


def write_json(report: dict[str, Any], path: str) -> None:
    payload = dict(report)
    payload["generated_at"] = _dt.datetime.now().isoformat(timespec="seconds")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2)


def print_summary(report: dict[str, Any]) -> None:
    if _RICH:
        _print_rich(report)
    else:
        _print_plain(report)


# ---------------------------------------------------------------------- #
def _print_rich(report: dict[str, Any]) -> None:
    console = Console()
    console.rule(f"[bold]Karabiber raporu — {report['target']} ({report['profile']})")

    modules = report.get("modules", {})

    # Portlar
    nmap = modules.get("nmap", {})
    if nmap.get("status") == "ok":
        table = Table(title="Açık Portlar", show_lines=False)
        table.add_column("Port", style="cyan")
        table.add_column("Servis", style="green")
        table.add_column("Ürün / Versiyon")
        for p in nmap.get("data", {}).get("open_ports", []):
            pv = f"{p.get('product','')} {p.get('version','')}".strip()
            table.add_row(f"{p['port']}/{p['protocol']}", p.get("service", ""), pv or "-")
        console.print(table)

    # Web servisleri
    services = modules.get("services", {})
    web = services.get("data", {}).get("web_services", []) if services.get("status") == "ok" else []
    if web:
        console.print(Panel("\n".join(w["url"] for w in web), title="Web Servisleri"))

    # gobuster yolları
    gob = modules.get("gobuster", {})
    if gob.get("status") == "ok":
        table = Table(title="Bulunan Yollar (gobuster + follow-up GET)")
        table.add_column("URL", style="cyan")
        table.add_column("Status")
        table.add_column("Boyut")
        for s in gob.get("data", {}).get("services", []):
            for f in s.get("findings", []):
                table.add_row(
                    f.get("url", f.get("path", "")),
                    str(f.get("followup_status", f.get("gobuster_status", "-"))),
                    str(f.get("followup_size", f.get("gobuster_size", "-"))),
                )
        if table.row_count:
            console.print(table)

    # Sızıntılar
    leaks = modules.get("leaks", {})
    if leaks.get("status") == "ok":
        hits = [h for s in leaks.get("data", {}).get("services", []) for h in s.get("hits", [])]
        if hits:
            console.print(
                Panel(
                    "\n".join(f"{h['url']} ({h['status']}, {h['size']}B)" for h in hits),
                    title="[red]Olası Sızıntılar / Yanlış Yapılandırma",
                    border_style="red",
                )
            )

    _print_errors_rich(console, modules)

    # AI paneli
    ai = report.get("ai", {})
    if ai.get("status") == "ok" and ai.get("suggestion"):
        console.print(
            Panel(
                ai["suggestion"],
                title="[yellow]AI Yorumu (ÖNERİ — doğrulanmamıştır)",
                border_style="yellow",
            )
        )
    elif ai.get("status") in ("unavailable", "disabled"):
        console.print(f"[dim]AI paneli atlandı ({ai.get('status')}).[/dim]")


def _print_errors_rich(console, modules) -> None:
    errs = [
        f"{name}: {m.get('error')}"
        for name, m in modules.items()
        if m.get("status") == "error" and m.get("error")
    ]
    if errs:
        console.print(
            Panel("\n".join(errs), title="[red]Hatalar", border_style="red")
        )


# ---------------------------------------------------------------------- #
def _print_plain(report: dict[str, Any]) -> None:
    print(f"\n=== Karabiber raporu — {report['target']} ({report['profile']}) ===\n")
    for name, m in report.get("modules", {}).items():
        print(f"[{name}] durum: {m.get('status')}")
        if m.get("error"):
            print(f"    HATA: {m['error']}")
        for note in m.get("notes", []):
            print(f"    - {note}")
    ai = report.get("ai", {})
    print(f"\n[AI] durum: {ai.get('status')}")
    if ai.get("suggestion"):
        print("--- AI ÖNERİSİ (doğrulanmamıştır) ---")
        print(ai["suggestion"])
