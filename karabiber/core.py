"""Orkestratör.

Modülleri MODULE_ORDER sırasıyla çalıştırır, her modülün sonucunu
context'e koyar ki sonraki modüller (gobuster/http/leaks) önceki
bulguları (web servisleri) kullanabilsin. İlerleme callback'i TUI veya
CLI tarafından dinlenebilir.
"""
from __future__ import annotations

import logging
from typing import Any, Callable

from .config import Config
from .llm import OllamaClient, build_findings_summary, LLMUnavailable
from .modules import MODULE_ORDER
from .modules.base import ModuleResult

# İlerleme olayları için callback tipi: (event_type, message)
ProgressCallback = Callable[[str, str], None]


class ReconEngine:
    def __init__(
        self,
        config: Config,
        profile: str | None = None,
        use_llm: bool = False,  # AI varsayılan olarak kapalı; --ai ile açılır
        progress: ProgressCallback | None = None,
    ) -> None:
        self.config = config
        self.profile = profile or config.default_profile
        self.use_llm = use_llm
        self.progress = progress or (lambda *_: None)
        self.log = logging.getLogger("karabiber.engine")
        self.results: dict[str, ModuleResult] = {}
        self.ai_suggestion: str | None = None
        self.ai_status: str = "pending"  # pending | ok | unavailable | disabled

    def _emit(self, event: str, message: str) -> None:
        self.progress(event, message)
        self.log.info("[%s] %s", event, message)

    def run(self, target: str) -> dict[str, Any]:
        self._emit("start", f"Hedef: {target} | Profil: {self.profile}")
        context: dict[str, Any] = {"profile": self.profile}

        for module_cls in MODULE_ORDER:
            module = module_cls(self.config, logging.getLogger(f"karabiber.{module_cls.name}"))
            self._emit("module_start", f"{module.name} başlıyor…")
            try:
                result = module.run(target, context)
            except Exception as exc:  # modül çökse bile zincir devam etsin
                self.log.exception("Modül %s beklenmedik hata", module.name)
                result = ModuleResult(
                    module=module.name, target=target, status="error", error=str(exc)
                )

            self.results[module.name] = result
            context[module.name] = result

            for note in result.notes:
                self._emit("note", f"[{module.name}] {note}")
            self._emit(
                "module_end",
                f"{module.name} bitti ({result.status})"
                + (f": {result.error}" if result.error else ""),
            )

        self._run_llm(target)
        self._emit("done", "Tarama tamamlandı.")
        return self.as_dict(target)

    # ------------------------------------------------------------------ #
    def _run_llm(self, target: str) -> None:
        if not self.use_llm:
            self.ai_status = "disabled"
            self._emit("ai", "AI katmanı kapalı (açmak için --ai).")
            return

        client = OllamaClient(self.config.llm)
        if not client.available():
            self.ai_status = "unavailable"
            self._emit("ai", "Ollama erişilemiyor; AI paneli atlandı (graceful degradation).")
            return

        self._emit("ai", f"Bulgular yorumlatılıyor ({client.model})…")
        findings = build_findings_summary(self.results)
        try:
            text = client.interpret(findings)
            self.ai_suggestion = text
            self.ai_status = "ok"
            self._emit("ai", "AI yorumu hazır (ÖNERİ niteliğindedir).")
        except LLMUnavailable as exc:
            self.ai_status = "unavailable"
            self._emit("ai", f"AI yorumu alınamadı: {exc}")

    def as_dict(self, target: str) -> dict[str, Any]:
        return {
            "target": target,
            "profile": self.profile,
            "modules": {name: r.to_dict() for name, r in self.results.items()},
            "ai": {
                "status": self.ai_status,
                "suggestion": self.ai_suggestion,
                "disclaimer": "AI çıktısı ÖNERİ'dir, doğrulanmamıştır.",
            },
        }
