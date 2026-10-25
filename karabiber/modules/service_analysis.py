"""Servis yorumlama.

Port NUMARASINA değil, nmap'in bildirdiği servis ADINA bakar. Böylece
8080'de çalışan http ya da 8443'te çalışan https gibi standart-dışı
portlardaki web servisleri de doğru tespit edilir.
"""
from __future__ import annotations

from typing import Any

from .base import STATUS_OK, STATUS_SKIPPED, ModuleResult, ReconModule

# Servis adında bu anahtarlar geçiyorsa web servisi say.
_HTTP_HINTS = ("http", "https", "http-proxy", "http-alt", "ssl/http", "www")
# TLS göstergeleri (scheme belirlemek için)
_TLS_HINTS = ("https", "ssl")


class ServiceAnalysisModule(ReconModule):
    name = "services"

    def run(self, target: str, context: dict[str, Any]) -> ModuleResult:
        result = self._result(target)

        nmap_res = context.get("nmap")
        if not nmap_res or nmap_res.status != STATUS_OK:
            result.status = STATUS_SKIPPED
            result.note("nmap sonucu yok; servis analizi atlandı.")
            return result

        open_ports: list[dict[str, Any]] = nmap_res.data.get("open_ports", [])
        web_services: list[dict[str, Any]] = []

        for p in open_ports:
            service = (p.get("service") or "").lower()
            tunnel = (p.get("tunnel") or "").lower()

            is_web = any(hint in service for hint in _HTTP_HINTS)
            if not is_web:
                continue

            # https mı http mi? Servis adı veya tunnel=ssl'e bak.
            is_tls = any(h in service for h in _TLS_HINTS) or "ssl" in tunnel
            scheme = "https" if is_tls else "http"
            host = nmap_res.data["hosts"][0]["address"] if nmap_res.data.get("hosts") else target
            host = host or target

            web_services.append(
                {
                    "port": p["port"],
                    "scheme": scheme,
                    "service": service,
                    "product": p.get("product", ""),
                    "url": f"{scheme}://{host}:{p['port']}",
                }
            )

        result.status = STATUS_OK
        result.data = {"web_services": web_services}
        if web_services:
            urls = ", ".join(w["url"] for w in web_services)
            result.note(f"{len(web_services)} web servisi: {urls}")
        else:
            result.note("Servis adlarına göre web servisi bulunamadı.")
        return result
