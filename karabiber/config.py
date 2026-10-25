"""Yapılandırma yükleme ve profil çözümleme.

Config bir YAML dosyasından okunur; profiller (nmap timing, gobuster
thread/delay) kodda sabit değil, tamamen bu dosyadan gelir.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any

import yaml


class ConfigError(Exception):
    """Config okuma / doğrulama hatası."""


@dataclass
class Profile:
    """Tek bir tarama profili (aggressive / normal / stealth)."""

    name: str
    description: str
    nmap_timing: str          # örn. "T4"  -> nmap'e "-T4" olarak geçer
    gobuster_threads: int
    gobuster_delay_ms: int
    # Profil bazlı opsiyonel ezmeler. None ise genel (Config) değer kullanılır.
    wordlist: str | None = None
    extensions: list[str] | None = None

    @property
    def nmap_timing_flag(self) -> str:
        """nmap komut satırı bayrağı: 'T4' -> '-T4'."""
        t = self.nmap_timing.strip().upper().lstrip("-")
        return f"-{t}"

    @property
    def gobuster_delay_arg(self) -> str | None:
        """gobuster --delay argümanı (ör. '400ms'); 0 ise None."""
        if self.gobuster_delay_ms and self.gobuster_delay_ms > 0:
            return f"{self.gobuster_delay_ms}ms"
        return None


@dataclass
class Config:
    """Tüm araç yapılandırması."""

    default_profile: str
    wordlist: str
    ports: str
    gobuster_extensions: list[str]
    http: dict[str, Any]
    leak_paths: list[str]
    llm: dict[str, Any]
    profiles: dict[str, Profile] = field(default_factory=dict)
    raw: dict[str, Any] = field(default_factory=dict)

    def get_profile(self, name: str | None = None) -> Profile:
        """Verilen (ya da varsayılan) profili döndür."""
        key = name or self.default_profile
        if key not in self.profiles:
            available = ", ".join(sorted(self.profiles))
            raise ConfigError(
                f"'{key}' profili tanımlı değil. Mevcut profiller: {available}"
            )
        return self.profiles[key]


DEFAULT_CONFIG_NAMES = ("config.yaml", "config.yml")


def _locate_default_config() -> str | None:
    """Proje kökünde varsayılan config dosyasını ara."""
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    for name in DEFAULT_CONFIG_NAMES:
        candidate = os.path.join(here, name)
        if os.path.isfile(candidate):
            return candidate
    return None


def load_config(path: str | None = None) -> Config:
    """Config dosyasını yükle ve doğrula.

    path verilmezse proje kökündeki config.yaml kullanılır.
    """
    path = path or _locate_default_config()
    if not path:
        raise ConfigError("Config dosyası bulunamadı (config.yaml?).")
    if not os.path.isfile(path):
        raise ConfigError(f"Config dosyası yok: {path}")

    try:
        with open(path, "r", encoding="utf-8") as fh:
            raw = yaml.safe_load(fh) or {}
    except yaml.YAMLError as exc:
        raise ConfigError(f"Config YAML parse hatası: {exc}") from exc

    try:
        profiles_raw = raw["profiles"]
        profiles = {
            name: Profile(
                name=name,
                description=p.get("description", ""),
                nmap_timing=p["nmap_timing"],
                gobuster_threads=int(p["gobuster_threads"]),
                gobuster_delay_ms=int(p.get("gobuster_delay_ms", 0)),
                wordlist=(p.get("wordlist") or None),
                extensions=(list(p["gobuster_extensions"]) if p.get("gobuster_extensions") else None),
            )
            for name, p in profiles_raw.items()
        }

        cfg = Config(
            default_profile=raw.get("default_profile", "aggressive"),
            wordlist=raw["wordlist"],
            ports=str(raw.get("ports", "default")),
            gobuster_extensions=list(raw.get("gobuster_extensions", [])),
            http=dict(raw.get("http", {})),
            leak_paths=list(raw.get("leak_paths", [])),
            llm=dict(raw.get("llm", {})),
            profiles=profiles,
            raw=raw,
        )
    except KeyError as exc:
        raise ConfigError(f"Config'te zorunlu alan eksik: {exc}") from exc

    if cfg.default_profile not in cfg.profiles:
        raise ConfigError(
            f"default_profile '{cfg.default_profile}' tanımlı profiller arasında yok."
        )
    return cfg
