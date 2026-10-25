"""HTTP / teknoloji analizi.

Her web servisi için başlıkları (Server, X-Powered-By vb.), cookie'leri,
robots.txt ve sitemap.xml içeriğini çeker. Amaç teknoloji parmak izi ve
gizli yol ipuçları toplamak.
"""
from __future__ import annotations

from typing import Any
from urllib.parse import urljoin

import requests

from .base import STATUS_OK, STATUS_SKIPPED, ModuleResult, ReconModule

# İlgilendiğimiz "fingerprint" başlıkları
_TECH_HEADERS = (
    "Server",
    "X-Powered-By",
    "X-AspNet-Version",
    "X-Generator",
    "Via",
    "X-Backend-Server",
)


class HttpAnalysisModule(ReconModule):
    name = "http"

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
            result.note("Web servisi yok; HTTP analizi atlandı.")
            return result

        http_cfg = self.config.http
        session = requests.Session()
        session.headers.update({"User-Agent": http_cfg.get("user_agent", "Karabiber")})

        analyses: list[dict[str, Any]] = []
        for svc in web_services:
            url = svc["url"]
            analyses.append(self._analyze(session, url, http_cfg, result))

        result.status = STATUS_OK
        result.data = {"services": analyses}
        return result

    # ------------------------------------------------------------------ #
    def _analyze(self, session, base_url, http_cfg, result) -> dict[str, Any]:
        info: dict[str, Any] = {"url": base_url}
        timeout = http_cfg.get("timeout", 8)
        verify = http_cfg.get("verify_tls", False)

        # 1) Ana sayfa başlıkları + cookie'ler
        try:
            resp = session.get(base_url, timeout=timeout, verify=verify)
            info["status"] = resp.status_code
            info["headers"] = {
                h: resp.headers[h] for h in _TECH_HEADERS if h in resp.headers
            }
            info["cookies"] = [
                {
                    "name": c.name,
                    "secure": c.secure,
                    "httponly": bool(c._rest.get("HttpOnly", False)),
                }
                for c in resp.cookies
            ]
            title = _extract_title(resp.text)
            if title:
                info["title"] = title
            tech = ", ".join(f"{k}={v}" for k, v in info["headers"].items())
            if tech:
                result.note(f"{base_url} -> {tech}")
        except requests.RequestException as exc:
            info["error"] = str(exc)
            return info

        # 2) robots.txt ve sitemap.xml
        info["robots_txt"] = self._fetch_text(session, base_url, "robots.txt", http_cfg)
        info["sitemap_xml"] = self._fetch_text(session, base_url, "sitemap.xml", http_cfg)

        if info["robots_txt"].get("found"):
            result.note(f"{base_url}/robots.txt mevcut ({info['robots_txt']['size']} bayt)")
        return info

    def _fetch_text(self, session, base_url, path, http_cfg) -> dict[str, Any]:
        url = urljoin(base_url + "/", path)
        try:
            resp = session.get(
                url,
                timeout=http_cfg.get("timeout", 8),
                verify=http_cfg.get("verify_tls", False),
            )
        except requests.RequestException as exc:
            return {"found": False, "error": str(exc)}

        found = resp.status_code == 200 and bool(resp.text.strip())
        out: dict[str, Any] = {
            "found": found,
            "status": resp.status_code,
            "size": len(resp.content),
        }
        if found:
            # İlk ~2KB yeterli; dev dosyaları raporu şişirmesin
            out["content"] = resp.text[:2048]
        return out


def _extract_title(html: str) -> str | None:
    lower = html.lower()
    start = lower.find("<title>")
    if start == -1:
        return None
    start += len("<title>")
    end = lower.find("</title>", start)
    if end == -1:
        return None
    return html[start:end].strip()[:120] or None
