"""Komut satırı arayüzü (argparse).

Varsayılan: config'teki default_profile (aggressive) ile çalışır,
sonuçları terminale basar. --tui ile Textual arayüzü açılır.
"""
from __future__ import annotations

import argparse
import logging
import sys

from . import __version__
from .banner import print_banner
from .config import ConfigError, load_config

_BANNER_WARNING = (
    "UYARI: Karabiber yalnızca YETKİLİ hedeflerde (kendi lab'ınız, "
    "TryHackMe/HTB, yazılı izinli pentest) kullanılmalıdır. İzinsiz "
    "tarama çoğu ülkede suçtur."
)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="yak",
        description="Karabiber (yak) — yetkili/legal ortamlar için modüler recon aracı.",
        epilog=_BANNER_WARNING,
    )
    p.add_argument("target", nargs="?", help="Hedef IP veya hostname")
    p.add_argument(
        "--profile",
        choices=["aggressive", "normal", "stealth"],
        help="Tarama profili (varsayılan: config'teki default_profile).",
    )
    p.add_argument("-c", "--config", help="Config dosyası yolu (vars: config.yaml)")
    p.add_argument("-o", "--output", help="JSON raporunun yazılacağı dosya")
    p.add_argument(
        "--ai",
        action="store_true",
        help="AI/LLM yorum katmanını AÇ (varsayılan: kapalı). Yerel Ollama gerektirir.",
    )
    p.add_argument("--tui", action="store_true", help="Textual TUI arayüzünü aç")
    p.add_argument(
        "--yes",
        action="store_true",
        help="Yetki onayını atla (sadece yetkili hedeflerde kullanın).",
    )
    p.add_argument("-v", "--verbose", action="store_true", help="Ayrıntılı log")
    p.add_argument("--version", action="version", version=f"Karabiber {__version__}")
    return p


def _setup_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.WARNING
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        stream=sys.stderr,
    )


def _confirm_authorization(target: str, assume_yes: bool) -> bool:
    print(_BANNER_WARNING, file=sys.stderr)
    if assume_yes:
        return True
    try:
        ans = input(f"'{target}' hedefini taramaya YETKİNİZ var mı? [e/H]: ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        return False
    return ans in ("e", "evet", "y", "yes")


def _prompt_target() -> str | None:
    """Hedef bayrağı verilmeden çalıştırıldığında interaktif karşılama.

    Banner'dan sonra kısa bir örnek gösterir ve hedefi sorar. Girdi bir
    terminale bağlı değilse (pipe/CI) None döner ki çağıran yardım bassın.
    """
    if not sys.stdin.isatty():
        return None
    print(
        "\nÖrnek:  yak 10.10.10.10 --profile stealth -o rapor.json\n"
        "Bayraklar: --profile {aggressive,normal,stealth}  --ai  --tui  -o DOSYA"
        "   (tümü için: yak -h)\n",
        file=sys.stderr,
    )
    try:
        target = input("Hedef IP / host (boş = çıkış): ").strip()
    except (EOFError, KeyboardInterrupt):
        print(file=sys.stderr)
        return None
    return target or None


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    _setup_logging(args.verbose)

    print_banner()

    target = args.target
    if not target:
        target = _prompt_target()
    if not target:
        # Interaktif değil ya da boş girildi: yardım bas, çık.
        if not sys.stdin.isatty():
            parser.print_help()
        return 2

    try:
        config = load_config(args.config)
    except ConfigError as exc:
        print(f"Config hatası: {exc}", file=sys.stderr)
        return 1

    profile = args.profile or config.default_profile
    try:
        config.get_profile(profile)  # erken doğrulama
    except ConfigError as exc:
        print(f"Profil hatası: {exc}", file=sys.stderr)
        return 1

    if not _confirm_authorization(target, args.yes):
        print("Onay verilmedi. Çıkılıyor.", file=sys.stderr)
        return 1

    # AI varsayılan olarak KAPALI; yalnızca --ai ile açılır.
    use_llm = args.ai

    # --- TUI yolu ---
    if args.tui:
        try:
            from .tui import run_tui
        except ImportError as exc:
            print(f"TUI için 'textual' gerekli: {exc}", file=sys.stderr)
            return 1
        run_tui(config, target, profile, use_llm, args.output)
        return 0

    # --- CLI yolu ---
    from .core import ReconEngine
    from .reporter import print_summary, write_json

    def progress(event: str, message: str) -> None:
        if args.verbose or event in ("note", "ai", "module_end", "done"):
            print(f"[{event}] {message}", file=sys.stderr)

    engine = ReconEngine(config, profile=profile, use_llm=use_llm, progress=progress)
    report = engine.run(target)

    print_summary(report)
    if args.output:
        write_json(report, args.output)
        print(f"\nJSON rapor: {args.output}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
