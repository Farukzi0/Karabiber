"""Sızıntı / yanlış-yapılandırma dosyası avı.

config.yaml'daki klasik yolları (.git/, .env, backup.zip, config.php.bak…)
her web servisi üzerinde dener. Hedefin "soft 404" (her şeye 200 dönen)
davranışını ayıklamak için önce rastgele bir yol ile temel çizgi (baseline)
ölçülür.
"""
from __future__ import annotations

import uuid
from typing import Any
from urllib.parse import urljoin

import requests

from .base import STATUS_OK, STATUS_SKIPPED, ModuleResult, ReconModule


class LeakHuntModule(ReconModule):
    name = "leaks"

    def run(self, target: str, context: dict[str, Any]) -> ModuleResult:
        result = self._result(target)

        services_res = context.get("services")
        web_services = (
            services_res.data.get("web_services", [])
            if services_res and services_res.status == STATUS_OK
            else []
        )
        if not web_services:
            result.status = STATUS_SKIPPED
            result.note("Web servisi yok; sızıntı avı atlandı.")
            return result

        http_cfg = self.config.http
        session = requests.Session()
        session.headers.update({"User-Agent": http_cfg.get("user_agent", "Karabiber")})

        per_service: list[dict[str, Any]] = []
        for svc in web_services:
            url = svc["url"]
            baseline = self._baseline(session, url, http_cfg)
            hits = self._hunt(session, url, http_cfg, baseline, result)
            per_service.append({"url": url, "hits": hits})

        result.status = STATUS_OK
        total = sum(len(s["hits"]) for s in per_service)
        result.data = {"services": per_service, "total_hits": total}
        if total:
            result.note(f"{total} olası sızıntı/yanlış-yapılandırma bulundu.")
        else:
            result.note("Klasik sızıntı yollarında buluntu yok.")
        return result

    # ------------------------------------------------------------------ #
    def _baseline(self, session, base_url, http_cfg) -> dict[str, Any]:
        """Var olmayan rastgele bir yolun davranışını ölç (soft-404 tespiti)."""
        rnd = urljoin(base_url + "/", f"karabiber-{uuid.uuid4().hex}.nonexistent")
        try:
            resp = session.get(
                rnd,
                timeout=http_cfg.get("timeout", 8),
                verify=http_cfg.get("verify_tls", False),
                allow_redirects=False,
            )
            return {"status": resp.status_code, "size": len(resp.content)}
        except requests.RequestException:
            return {"status": None, "size": None}

    def _hunt(self, session, base_url, http_cfg, baseline, result) -> list[dict[str, Any]]:
        hits: list[dict[str, Any]] = []
        for path in self.config.leak_paths:
            url = urljoin(base_url + "/", path.lstrip("/"))
            try:
                resp = session.get(
                    url,
                    timeout=http_cfg.get("timeout", 8),
                    verify=http_cfg.get("verify_tls", False),
                    allow_redirects=False,
                )
            except requests.RequestException:
                continue

            if not self._is_interesting(resp, baseline):
                continue

            hit = {
                "path": path,
                "url": url,
                "status": resp.status_code,
                "size": len(resp.content),
            }
            hits.append(hit)
            result.note(f"Sızıntı ipucu: {url} ({resp.status_code}, {hit['size']} bayt)")
        return hits

    @staticmethod
    def _is_interesting(resp, baseline) -> bool:
        """200 dönen ve baseline'dan (soft-404) belirgin farklı yanıtlar."""
        if resp.status_code != 200:
            return False
        size = len(resp.content)
        # Hedef her şeye aynı boyutta 200 dönüyorsa bu gerçek bir buluntu değildir.
        if baseline.get("status") == 200 and baseline.get("size") == size:
            return False
        return True
