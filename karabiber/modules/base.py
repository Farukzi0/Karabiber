"""Ortak modül arayüzü.

Her recon modülü ReconModule'ü miras alır ve `run(target, context)`
uygular. Dönüş her zaman standart bir ModuleResult'tır; böylece
raporlayıcı ve TUI tüm modülleri aynı şekilde işleyebilir ve yeni
modül eklemek sadece bu arayüzü uygulamakla mümkün olur.
"""
from __future__ import annotations

import abc
import logging
from dataclasses import asdict, dataclass, field
from typing import Any


# Modül çalışma durumları
STATUS_OK = "ok"
STATUS_ERROR = "error"
STATUS_SKIPPED = "skipped"


@dataclass
class ModuleResult:
    """Tek bir modülün ürettiği standart sonuç."""

    module: str
    target: str
    status: str = STATUS_OK
    data: dict[str, Any] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)
    error: str | None = None

    def note(self, message: str) -> None:
        """İnsan tarafından okunacak kısa bir not ekle."""
        self.notes.append(message)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class ReconModule(abc.ABC):
    """Tüm recon modüllerinin ortak taban sınıfı.

    Alt sınıflar `name` ve `run()` sağlamak zorundadır.
    """

    #: Modülün kısa, benzersiz adı (rapor anahtarı olarak kullanılır)
    name: str = "base"

    def __init__(self, config, logger: logging.Logger | None = None) -> None:
        self.config = config
        self.log = logger or logging.getLogger(f"karabiber.{self.name}")

    @abc.abstractmethod
    def run(self, target: str, context: dict[str, Any]) -> ModuleResult:
        """Modülü hedef üzerinde çalıştır.

        context: önceki modüllerin sonuçları (örn. nmap -> web portları).
        Yeni modül ekleyenler bu context'i okuyarak zincir kurabilir.
        """
        raise NotImplementedError

    # Alt sınıflar için kolaylık yardımcıları ------------------------------

    def _result(self, target: str, **kwargs: Any) -> ModuleResult:
        return ModuleResult(module=self.name, target=target, **kwargs)
