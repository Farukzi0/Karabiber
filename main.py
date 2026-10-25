#!/usr/bin/env python3
"""Karabiber giriş noktası (geliştirme / kurulum gerektirmeyen çalıştırma).

Kullanım:
    python main.py <hedef> [--profile ...] [--tui] [-o rapor.json]

Kurulumdan sonra (pip install -e .) aynı araç 'yak' komutuyla çağrılır:
    yak <hedef> ...          # tarama
    karabiber                # sadece banner (splash)
"""
from karabiber.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
