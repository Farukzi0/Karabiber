"""nmap sarmalayıcı.

nmap'i subprocess ile çalıştırır, XML çıktısını (-oX) xml.etree ile
parse eder. python-nmap KULLANILMAZ; XML'i doğrudan biz işleriz, böylece
bağımlılık azalır ve çıktının hangi alanlarını okuduğumuz tamamen bizim
kontrolümüzde olur.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import xml.etree.ElementTree as ET
from typing import Any

from .base import STATUS_ERROR, STATUS_OK, ModuleResult, ReconModule


class NmapModule(ReconModule):
    name = "nmap"

    def run(self, target: str, context: dict[str, Any]) -> ModuleResult:
        result = self._result(target)

        # 1) nmap kurulu mu? Değilse anlamlı mesajla çık.
        if shutil.which("nmap") is None:
            result.status = STATUS_ERROR
            result.error = (
                "nmap bulunamadı. Kurulum: 'sudo apt install nmap' "
                "(Debian/Kali) veya dağıtımınızın paket yöneticisi."
            )
            return result

        profile = self.config.get_profile(context.get("profile"))

        # 2) XML çıktısı için geçici dosya. delete=False çünkü nmap'in
        #    yazması bittikten sonra biz okuyacağız.
        tmp = tempfile.NamedTemporaryFile(
            prefix="karabiber_nmap_", suffix=".xml", delete=False
        )
        tmp.close()
        xml_path = tmp.name

        cmd = ["nmap", "-sV", profile.nmap_timing_flag, "-oX", xml_path]
        if self.config.ports and self.config.ports != "default":
            cmd += ["-p", self.config.ports]
        cmd.append(target)

        self.log.info("nmap komutu: %s", " ".join(cmd))
        result.note(f"Komut: {' '.join(cmd)}")

        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=1800,  # 30 dk güvenlik tavanı
                check=False,
            )
        except subprocess.TimeoutExpired:
            result.status = STATUS_ERROR
            result.error = "nmap zaman aşımına uğradı (>30dk)."
            self._cleanup(xml_path)
            return result
        except OSError as exc:
            result.status = STATUS_ERROR
            result.error = f"nmap başlatılamadı: {exc}"
            self._cleanup(xml_path)
            return result

        if proc.returncode != 0:
            # nmap bazen kısmi çıktı üretir; yine de XML'i okumayı deneriz
            self.log.warning(
                "nmap sıfırdan farklı kod döndü (%s): %s",
                proc.returncode,
                proc.stderr.strip(),
            )
            result.note(f"nmap uyarısı: {proc.stderr.strip()[:200]}")

        # 3) XML'i parse et
        try:
            hosts = self._parse_xml(xml_path)
        except (ET.ParseError, FileNotFoundError) as exc:
            result.status = STATUS_ERROR
            result.error = f"nmap XML parse edilemedi: {exc}"
            self._cleanup(xml_path)
            return result
        finally:
            self._cleanup(xml_path)

        ports = [p for h in hosts for p in h["ports"]]
        result.status = STATUS_OK
        result.data = {
            "profile": profile.name,
            "timing": profile.nmap_timing_flag,
            "hosts": hosts,
            "open_ports": ports,
            "open_port_count": len(ports),
        }
        if ports:
            summary = ", ".join(f"{p['port']}/{p['service']}" for p in ports)
            result.note(f"{len(ports)} açık port: {summary}")
        else:
            result.note("Açık port bulunamadı (hedef kapalı/filtreli olabilir).")
        return result

    # ------------------------------------------------------------------ #
    # XML PARSE
    # ------------------------------------------------------------------ #
    def _parse_xml(self, xml_path: str) -> list[dict[str, Any]]:
        """nmap XML çıktısını yapılandırılmış dict listesine çevir.

        İlgilendiğimiz XML iskeleti:
            <nmaprun>
              <host>
                <status state="up"/>
                <address addr="10.10.10.10" addrtype="ipv4"/>
                <ports>
                  <port protocol="tcp" portid="80">
                    <state state="open" .../>
                    <service name="http" product="Apache httpd"
                             version="2.4.41" tunnel="ssl" .../>
                  </port>
                </ports>
              </host>
            </nmaprun>
        """
        tree = ET.parse(xml_path)
        root = tree.getroot()

        hosts: list[dict[str, Any]] = []
        for host_el in root.findall("host"):
            # Host up değilse atla
            status_el = host_el.find("status")
            if status_el is not None and status_el.get("state") != "up":
                continue

            address = self._extract_address(host_el)
            ports: list[dict[str, Any]] = []

            ports_el = host_el.find("ports")
            if ports_el is not None:
                for port_el in ports_el.findall("port"):
                    state_el = port_el.find("state")
                    # Sadece gerçekten AÇIK portları al.
                    if state_el is None or state_el.get("state") != "open":
                        continue

                    svc_el = port_el.find("service")
                    service_name = svc_el.get("name", "") if svc_el is not None else ""
                    ports.append(
                        {
                            "port": int(port_el.get("portid")),
                            "protocol": port_el.get("protocol", "tcp"),
                            "service": service_name,
                            "product": (svc_el.get("product", "") if svc_el is not None else ""),
                            "version": (svc_el.get("version", "") if svc_el is not None else ""),
                            # tunnel="ssl" -> servis TLS üzerinde demektir (https tespiti için)
                            "tunnel": (svc_el.get("tunnel", "") if svc_el is not None else ""),
                        }
                    )

            hosts.append({"address": address, "ports": ports})
        return hosts

    @staticmethod
    def _extract_address(host_el: ET.Element) -> str:
        """Host için tercihen IPv4 adresini çıkar."""
        ipv4 = ""
        fallback = ""
        for addr_el in host_el.findall("address"):
            addr = addr_el.get("addr", "")
            if addr_el.get("addrtype") == "ipv4":
                ipv4 = addr
            elif not fallback:
                fallback = addr
        return ipv4 or fallback

    @staticmethod
    def _cleanup(path: str) -> None:
        try:
            os.unlink(path)
        except OSError:
            pass
