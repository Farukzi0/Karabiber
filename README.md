# Karabiber 🌶️

Eğitim ve CTF (TryHackMe / HTB easy box) ortamları için modüler bir **recon
(keşif) otomasyonu** aracı. Bir hedefin keşif aşamasını otomatikleştirir,
bulguları yapılandırılmış biçimde raporlar ve (opsiyonel) yerel bir LLM ile
"sıradaki adım" önerileri üretir.

---

## ⚖️ Yasal Uyarı — ÖNCE OKUYUN

> **Karabiber yalnızca YETKİLİ ve YASAL ortamlarda kullanılmak içindir.**
>
> - Kendi laboratuvarınız, TryHackMe / Hack The Box gibi izinli platformlar,
>   veya **yazılı izniniz olan** sistemler.
> - Sahibi olmadığınız ya da yazılı izniniz bulunmayan sistemleri taramak
>   (port taraması, dizin brute-force vb.) **çoğu ülkede suçtur** (ör. TR
>   5237 s. TCK 243–244, ABD CFAA, UK Computer Misuse Act).
> - Araç her çalıştırmada yetki onayı ister (`--yes` ile atlanabilir;
>   sorumluluk tamamen kullanıcıya aittir).
>
> Bu aracı kullanan kişi, hedef üzerinde test yapma yetkisine sahip
> olduğunu beyan etmiş sayılır. Yazarlar kötüye kullanımdan sorumlu değildir.

---

## Özellikler

- **nmap sarmalayıcı** — `subprocess` ile `nmap -sV -oX`, çıktıyı `xml.etree`
  ile parse eder (python-nmap kullanılmaz). Açık portlar + servis adları.
- **Servis yorumlama** — Port numarasına değil, **servis adına** bakar;
  8080/8443 gibi standart-dışı portlardaki web servislerini de yakalar.
- **gobuster sarmalayıcı** — Yalnızca web servisi olan portlara `gobuster dir`
  (`-x php,html,txt,bak`). Her buluntuya follow-up GET → status + boyut.
- **HTTP / teknoloji analizi** — `Server`, `X-Powered-By`, cookie'ler,
  `robots.txt`, `sitemap.xml`.
- **Sızıntı avı** — `.git/`, `.env`, `backup.zip`, `config.php.bak` gibi
  klasik yollar (soft-404 filtresiyle).
- **Raporlayıcı** — JSON + renkli terminal özeti.
- **LLM katmanı (opsiyonel, varsayılan KAPALI)** — Yerel Ollama'ya bulguları
  yorumlatır. Yalnızca `--ai` bayrağı verilince çalışır; yavaş makineleri
  yormamak için varsayılan olarak devre dışıdır. Ollama yoksa araç normal
  çalışır, panel atlanır (graceful degradation). Çıktı daima **"ÖNERİ"**
  olarak işaretlenir, kesin gerçek gibi sunulmaz.
- **TUI** — Textual: üstte pyfiglet logo, solda canlı log, sağda AI paneli.

## Mimari

```
main.py                      → giriş noktası
karabiber/
  cli.py                     → argparse CLI, yetki onayı
  config.py                  → config.yaml yükleme + profiller
  core.py                    → orkestratör (modülleri zincirler)
  llm.py                     → Ollama istemcisi (opsiyonel)
  banner.py                  → pyfiglet ASCII logo (CLI + TUI ortak)
  reporter.py                → JSON + terminal raporu
  tui.py                     → Textual arayüzü
  modules/
    base.py                  → ReconModule arayüzü: run(target, context) -> ModuleResult
    nmap_scan.py             → nmap + XML parse
    service_analysis.py      → servis adına göre web tespiti
    gobuster_scan.py         → gobuster + follow-up GET
    http_analysis.py         → başlık/cookie/robots/sitemap
    leak_hunt.py             → sızıntı dosyası avı
config.yaml                  → tüm ayarlar (wordlist, portlar, profiller, LLM)
```

**Modüler tasarım:** Her modül ortak `run(target, context) -> ModuleResult`
arayüzünü uygular. `context`, önceki modüllerin sonuçlarını taşır (nmap →
servisler → gobuster/http/leaks). Yeni modül eklemek için `ReconModule`'ü
uygulayıp `modules/__init__.py` içindeki `MODULE_ORDER`'a eklemek yeterli.

## Kurulum

```bash
# Python bağımlılıkları
pip install -r requirements.txt

# Harici araçlar (Python paketi değildir!)
sudo apt install nmap gobuster      # Debian / Kali

# (Opsiyonel) AI katmanı için Ollama
#   https://ollama.com  → kurduktan sonra:
ollama pull qwen2.5:3b
```

`config.yaml` içindeki `wordlist` yolunu kendi ortamınıza göre düzenleyin
(ör. SecLists). Her profil kendi `wordlist` / `gobuster_extensions` değerini
verip bunu ezebilir. AI katmanı **varsayılan olarak kapalıdır**; açmak için
`--ai` bayrağını kullanın (Ollama gerektirir).

## Kullanım

```bash
# Varsayılan (aggressive) profil, terminal raporu
python main.py 10.10.10.10

# Profil + JSON çıktısı
python main.py 10.10.10.10 --profile stealth -o rapor.json

# TUI
python main.py 10.10.10.10 --tui

# AI yorum katmanını AÇ (yerel Ollama gerekir), onayı atla (yetkili lab)
python main.py 10.10.10.10 --ai --yes
```

## Tarama Profilleri

Profiller `config.yaml`'da tanımlıdır (kodda hardcoded değil). nmap zamanlama
şablonunu ve gobuster thread/delay değerlerini **birlikte** ayarlar.

| Profil | nmap | gobuster | Ne zaman? |
|--------|------|----------|-----------|
| **aggressive** (varsayılan) | `-T4` | 80 thread, 0ms delay | **CTF / izole lab.** Hız öncelikli, gürültü umursanmaz. Kısa wordlist + az uzantı. |
| **normal** | `-T3` | 30 thread, 50ms delay | Dengeli. Yetkili ama paylaşımlı test ortamları. |
| **stealth** | `-T1` | 5 thread, 400ms delay | **IDS/WAF'tan kaçınma**, rate-limit / IP-ban riski olan yetkili gerçek hedefler. Yavaş ama sessiz. |

> **Neden önemli:** CTF'te `aggressive` idealdir. Gerçek bir pentest
> hedefinde `aggressive` kullanmak WAF tetikleyebilir, IP'nizi bandan geçirir
> veya rate-limit'e takılırsınız — orada `stealth` tercih edin.

## Örnek Çıktı (kısaltılmış)

Terminal:

```
──────── Karabiber raporu — 10.10.10.10 (aggressive) ────────
         Açık Portlar
┏━━━━━━━━┳━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━┓
┃ Port   ┃ Servis  ┃ Ürün / Versiyon     ┃
┡━━━━━━━━╇━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━┩
│ 22/tcp │ ssh     │ OpenSSH 8.2p1       │
│ 80/tcp │ http    │ Apache httpd 2.4.41 │
└────────┴─────────┴─────────────────────┘
╭─ Web Servisleri ─╮
│ http://10.10.10.10:80 │
╰──────────────────╯
╭─ Olası Sızıntılar ─╮
│ http://10.10.10.10:80/.git/HEAD (200, 23B) │
╰────────────────────╯
╭─ AI Yorumu (ÖNERİ — doğrulanmamıştır) ─╮
│ DURUM ÖZETİ: 80/tcp'de Apache... .git açık olabilir.
│ SIRADAKİ ADIMLAR:
│  - /.git dizini git-dumper ile çekilebilir
│  - gobuster uzantılarına 'phps,old' eklenebilir
╰────────────────────────────────────────╯
```

JSON (`-o rapor.json`): tüm modül sonuçları + AI önerisi, makine-okur formatta.

## Lisans / Sorumluluk

Eğitim amaçlıdır. Kullanımdan doğacak tüm sorumluluk kullanıcıya aittir.
Yetkiniz olmayan sistemlerde **kullanmayın**.
