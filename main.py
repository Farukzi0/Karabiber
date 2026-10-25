#!/usr/bin/env python3
"""Karabiber giriş noktası.

Kullanım:
    python main.py <hedef> [--profile ...] [--tui] [-o rapor.json]
veya paket olarak:
    python -m karabiber.cli <hedef> ...
"""
from karabiber.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
