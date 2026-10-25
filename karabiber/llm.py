"""LLM katmanı (opsiyonel) - Ollama üzerinden yorumlama.

Ham bulguları yerel Ollama sunucusuna gönderip bir özet ve "sıradaki adım"
önerisi alır. Ollama yoksa/erişilemezse sessizce devre dışı kalır
(graceful degradation): araç normal çalışır, yalnızca bu panel atlanır.

ÖNEMLİ: Çıktı her zaman ÖNERİ'dir; kesin gerçek olarak sunulmaz.
"""
from __future__ import annotations

import json
import logging
from typing import Any

import requests

log = logging.getLogger("karabiber.llm")

_SYSTEM = (
    "Sen yetkili bir sızma testi / CTF ortamında çalışan bir asistansın. "
    "Sana verilen recon bulgularını yorumla. Türkçe yanıt ver. "
    "Yanıtın iki kısım olsun: (1) kısa DURUM ÖZETİ, (2) 'SIRADAKİ ADIMLAR' "
    "başlığı altında 3-5 maddelik somut öneri. Öneriler spekülatiftir; "
    "kesin gerçek gibi sunma, 'olabilir / denenebilir' dilini kullan. "
    "Sadece yetkili hedefler varsayılır."
)


class LLMUnavailable(Exception):
    """Ollama erişilemediğinde yükseltilir."""


class OllamaClient:
    def __init__(self, llm_cfg: dict[str, Any]) -> None:
        self.enabled = bool(llm_cfg.get("enabled", True))
        self.base_url = llm_cfg.get("base_url", "http://localhost:11434").rstrip("/")
        self.model = llm_cfg.get("model", "qwen2.5:3b")
        self.timeout = int(llm_cfg.get("timeout", 60))
        self.temperature = float(llm_cfg.get("temperature", 0.2))

    def available(self) -> bool:
        """Ollama ayakta mı? (hızlı kontrol)"""
        if not self.enabled:
            return False
        try:
            resp = requests.get(f"{self.base_url}/api/tags", timeout=5)
            return resp.status_code == 200
        except requests.RequestException:
            return False

    def interpret(self, findings: dict[str, Any]) -> str:
        """Bulguları yorumlat; erişilemezse LLMUnavailable fırlat."""
        if not self.enabled:
            raise LLMUnavailable("LLM config'te kapalı.")

        prompt = (
            f"{_SYSTEM}\n\n"
            "=== RECON BULGULARI (JSON) ===\n"
            f"{json.dumps(findings, ensure_ascii=False, indent=2)}\n"
            "=== BULGULAR SONU ===\n\n"
            "Yukarıdaki bulguları yorumla."
        )
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": self.temperature},
        }
        try:
            resp = requests.post(
                f"{self.base_url}/api/generate",
                json=payload,
                timeout=self.timeout,
            )
        except requests.RequestException as exc:
            raise LLMUnavailable(f"Ollama'ya ulaşılamadı: {exc}") from exc

        if resp.status_code == 404:
            raise LLMUnavailable(
                f"Model '{self.model}' bulunamadı. 'ollama pull {self.model}' deneyin."
            )
        if resp.status_code != 200:
            raise LLMUnavailable(f"Ollama hata kodu {resp.status_code}: {resp.text[:200]}")

        try:
            data = resp.json()
        except ValueError as exc:
            raise LLMUnavailable(f"Ollama yanıtı JSON değil: {exc}") from exc

        text = (data.get("response") or "").strip()
        if not text:
            raise LLMUnavailable("Ollama boş yanıt döndü.")
        return text


def build_findings_summary(results: dict[str, Any]) -> dict[str, Any]:
    """Modül sonuçlarını LLM'e verilecek sade bir özete indirge.

    Ham HTTP gövdeleri gibi büyük/gürültülü alanlar dışarıda bırakılır.
    """
    summary: dict[str, Any] = {}

    nmap = results.get("nmap")
    if nmap and nmap.status == "ok":
        summary["open_ports"] = [
            {"port": p["port"], "service": p["service"], "product": p.get("product", "")}
            for p in nmap.data.get("open_ports", [])
        ]

    services = results.get("services")
    if services and services.status == "ok":
        summary["web_services"] = services.data.get("web_services", [])

    gobuster = results.get("gobuster")
    if gobuster and gobuster.status == "ok":
        summary["discovered_paths"] = [
            {"url": f.get("url"), "status": f.get("followup_status"), "size": f.get("followup_size")}
            for s in gobuster.data.get("services", [])
            for f in s.get("findings", [])
        ]

    http = results.get("http")
    if http and http.status == "ok":
        summary["http_tech"] = [
            {"url": s.get("url"), "headers": s.get("headers", {}), "title": s.get("title")}
            for s in http.data.get("services", [])
        ]

    leaks = results.get("leaks")
    if leaks and leaks.status == "ok":
        summary["leaks"] = [
            {"url": h.get("url"), "status": h.get("status")}
            for s in leaks.data.get("services", [])
            for h in s.get("hits", [])
        ]

    return summary
