"""gobuster sarmalayıcı.

Sadece servis analizinde web servisi bulunan portlara 'gobuster dir'
çalıştırır. Bulunan her yola requests ile follow-up GET atıp status
kodu + gövde boyutunu raporlar.
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
from typing import Any
from urllib.parse import urljoin

import requests

from .base import STATUS_ERROR, STATUS_OK, STATUS_SKIPPED, ModuleResult, ReconModule

# gobuster "quiet" çıktı satırı: "/admin (Status: 301) [Size: 312]"
_LINE_RE = re.compile(r"^(?P<path>\S+)\s+\(Status:\s*(?P<status>\d+)\)\s*\[Size:\s*(?P<size>\d+)\]")


class GobusterModule(ReconModule):
    name = "gobuster"

    def run(self, target: str, context: dict[str, Any]) -> ModuleResult:
        result = self._result(target)

        if shutil.which("gobuster") is None:
            result.status = STATUS_ERROR
            result.error = (
                "gobuster bulunamadı. Kurulum: 'sudo apt install gobuster' "
                "ya da 'go install github.com/OJ/gobuster/v3@latest'."
            )
            return result

        services_res = context.get("services")
        web_services = (
            services_res.data.get("web_services", [])
            if services_res and services_res.status == STATUS_OK
            else []
        )
        if not web_services:
            result.status = STATUS_SKIPPED
            result.note("Web servisi yok; gobuster atlandı.")
            return result

        profile = self.config.get_profile(context.get("profile"))

        # Wordlist ve uzantılar profil bazlı ezilebilir; yoksa genel ayara düşer.
        # Küçük liste + az uzantı = daha az istek = daha hızlı tarama.
        wordlist = profile.wordlist or self.config.wordlist
        extensions = ",".join(profile.extensions or self.config.gobuster_extensions)
        if not os.path.isfile(wordlist):
            result.status = STATUS_ERROR
            result.error = f"Kelime listesi bulunamadı: {wordlist} (config.yaml -> wordlist)"
            return result

        http_cfg = self.config.http
        session = _build_session(http_cfg)

        per_service: list[dict[str, Any]] = []
        for svc in web_services:
            url = svc["url"]
            self.log.info("gobuster -> %s", url)
            result.note(f"gobuster taranıyor: {url}")
            findings = self._scan_one(url, wordlist, extensions, profile, result)
            # Her buluntuya follow-up GET
            for f in findings:
                self._followup(session, url, f, http_cfg)
            per_service.append({"url": url, "findings": findings})

        result.status = STATUS_OK
        total = sum(len(s["findings"]) for s in per_service)
        result.data = {"services": per_service, "total_paths": total}
        result.note(f"Toplam {total} yol bulundu.")
        return result

    # ------------------------------------------------------------------ #
    def _scan_one(self, url, wordlist, extensions, profile, result) -> list[dict[str, Any]]:
        cmd = [
            "gobuster", "dir",
            "-u", url,
            "-w", wordlist,
            "-x", extensions,
            "-t", str(profile.gobuster_threads),
            "--timeout", "10s",  # askıda kalan isteğin tüm taramayı yavaşlatmasını önler
            "-q",            # quiet: sadece buluntular
            "-k",            # self-signed TLS'i yoksay (lab)
            "--no-error",
        ]
        delay = profile.gobuster_delay_arg
        if delay:
            cmd += ["--delay", delay]

        try:
            proc = subprocess.run(
                cmd, capture_output=True, text=True, timeout=1800, check=False
            )
        except subprocess.TimeoutExpired:
            result.note(f"gobuster zaman aşımı: {url}")
            return []
        except OSError as exc:
            result.note(f"gobuster çalıştırılamadı: {exc}")
            return []

        findings: list[dict[str, Any]] = []
        for line in proc.stdout.splitlines():
            m = _LINE_RE.match(line.strip())
            if m:
                findings.append(
                    {
                        "path": m.group("path"),
                        "gobuster_status": int(m.group("status")),
                        "gobuster_size": int(m.group("size")),
                    }
                )
        return findings

    def _followup(self, session, base_url, finding, http_cfg) -> None:
        """Bulunan yola doğrudan GET atıp güncel status + boyut al."""
        full = urljoin(base_url + "/", finding["path"].lstrip("/"))
        finding["url"] = full
        try:
            resp = session.get(
                full,
                timeout=http_cfg.get("timeout", 8),
                verify=http_cfg.get("verify_tls", False),
                allow_redirects=False,
            )
            finding["followup_status"] = resp.status_code
            finding["followup_size"] = len(resp.content)
            loc = resp.headers.get("Location")
            if loc:
                finding["redirect_to"] = loc
        except requests.RequestException as exc:
            finding["followup_status"] = None
            finding["followup_error"] = str(exc)


def _build_session(http_cfg: dict[str, Any]) -> requests.Session:
    s = requests.Session()
    s.headers.update({"User-Agent": http_cfg.get("user_agent", "Karabiber")})
    return s
