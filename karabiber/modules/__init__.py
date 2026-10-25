"""Recon modülleri.

MODULE_ORDER zinciri belirler: nmap -> services -> (gobuster, http, leaks).
Yeni bir modül eklemek için ReconModule'ü uygulayıp buraya ekleyin.
"""
from .base import ModuleResult, ReconModule
from .gobuster_scan import GobusterModule
from .http_analysis import HttpAnalysisModule
from .leak_hunt import LeakHuntModule
from .nmap_scan import NmapModule
from .service_analysis import ServiceAnalysisModule

# Çalışma sırası (context zincirine göre)
MODULE_ORDER = [
    NmapModule,
    ServiceAnalysisModule,
    GobusterModule,
    HttpAnalysisModule,
    LeakHuntModule,
]

__all__ = [
    "ReconModule",
    "ModuleResult",
    "MODULE_ORDER",
    "NmapModule",
    "ServiceAnalysisModule",
    "GobusterModule",
    "HttpAnalysisModule",
    "LeakHuntModule",
]
