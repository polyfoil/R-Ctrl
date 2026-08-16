**Dil / Language:** [English](README.md) · **Türkçe**

# R-Ctrl — Whisperer (local)

**R-Ctrl — Whisperer**, yerel Windows diktesidir: kısayolu basılı tutun, konuşun, makinede **Whisper** (faster-whisper) ile metne çevirin, odaktaki uygulamaya **yapıştırın**. Varsayılan kısayol: **Sağ Ctrl** (`R-Ctrl`). Ses cihazdan çıkmaz; widget için API anahtarı gerekmez.

## Gereksinimler

- **Windows 10/11**
- **Python 3.11+** (geliştirme 3.13 ile test edildi)
- **NVIDIA GPU** önerilir (VRAM’e göre `large-v3` / `medium` / `small`; GPU yoksa CPU + `small`)
- İlk çalıştırmada model **Hugging Face Hub**’dan indirilir (**~3 GB**’a kadar; herkese açık modeller için HF API anahtarı gerekmez)
- Global kısayol ve yapıştırma için **`rctrl_widget.bat` yönetici (UAC) ile** çalıştırılmalıdır

## Hızlı başlangıç (widget — ana mod)

```text
setup_widget.bat    # bir kez: bağımlılıklar
rctrl_widget.bat    # UAC → Evet
```

Terminalde `Model ready:` satırını görünce kapsül **R-Ctrl · Hazır** olur:

- **Sağ Ctrl** basılı tut = push-to-talk; kısa dokunuş = el değmeden aç/kapa
- Kapsüle **tıkla** = kayıt başlat/durdur
- **Sağ tık** = model, mikrofon, dil, geçmiş (`inbox.json`)
- **Sistem tepsisi** = çift tık göster/gizle, sağ tık menü

### Doğru giriş noktası

| Kullan | Kullanma |
|--------|----------|
| `rctrl_widget.bat` | `python rctrl_widget.py` (IDE Run) |
| `python launch_widget.py` | Aynı anda iki kopya |

`rctrl_widget.bat` → `launch_widget.py`: önce Whisper/CUDA, sonra PyQt6. İkinci açılış “zaten çalışıyor” ile kapanır.

### Model önbelleği

Ağırlıklar repoya **yazılmaz**. Varsayılan konum:

```text
%USERPROFILE%\.cache\huggingface\hub
```

İsteğe bağlı: `HF_HOME` veya `HUGGINGFACE_HUB_CACHE`. Rate limit veya kapalı modeller için `HF_TOKEN` veya `huggingface-cli login`.

### İsteğe bağlı

```text
set RCTRL_NO_TRAY=1
rctrl_widget.bat
```

## Diğer modlar

| Komut | Açıklama |
|--------|----------|
| `setup_server.bat` + `rctrl_server.bat` | Tarayıcı UI: http://127.0.0.1:5000 (yalnızca localhost) |
| `setup.bat` + `rctrl.bat` | **Eski** — OpenAI Whisper API (`OPENAI_API_KEY`) |

Sunucu **127.0.0.1**’e bağlıdır. Transkripsiyon **Save to Inbox** ile `inbox.json`'a kaydedilir (tuş enjeksiyonu yok). **0.0.0.0’a bağlamayın** (token + TLS olmadan).

## İndir (çoğu kullanıcı için önerilen)

1. **GitHub Releases** → `R-Ctrl-Whisperer-win64.zip` indirin.
2. İstediğiniz yere açın (ör. `Masaüstü\R-Ctrl-Whisperer`).
3. **`Start-R-Ctrl-Whisperer.bat`** çalıştırın, **UAC** onaylayın (global kısayol için yönetici gerekir).
4. İlk açılışta Whisper modeli iner (~3 GB). `config.json` ve `inbox.json` **`.exe` ile aynı klasörde** oluşur.
5. Günlük: `%LOCALAPPDATA%\R-Ctrl\widget.log` (konsol penceresi yok).

Zip üretimi: `packaging\build_widget.ps1` (`dist/README.tr.md`).

## Kaynaktan kurulum (geliştiriciler)

```bash
git clone <repo-url>
cd R-Ctrl
setup_widget.bat
rctrl_widget.bat
```

Geliştirme:

```bash
python -m pip install -r requirements-dev.txt
python -m pytest
python -m ruff check .
python -m mypy
```

`config.json`, `inbox.json` ve model önbelleği commit edilmez.

## Proje yapısı

| Yol | Rol |
|-----|-----|
| `core/` | Ses, motor, metin, enjeksiyon, geçmiş — Qt/FastAPI yok |
| `launch_widget.py` | CUDA-first widget başlatıcı |
| `rctrl_widget.py` | Kapsül + tepsi + kablolama |
| `rctrl_controller.py` | Qt’siz dikte durum makinesi |
| `rctrl_server.py` | Yerel HTTP dikte |
| `rctrl.py` | İsteğe bağlı bulut CLI |
| `tests/` | Birim ve duman testleri |
| `dist/` | Release zip çıktısı (gitignore); `dist/README.tr.md` |
| `packaging/` | PyInstaller spec + `build_widget.ps1` |

### `R-Ctrl-Widget/` klasörünü kullanmayın

Repo kökündeki bu klasör **eski / zip’ten çıkan kopyadır** (gitignore). Yalnızca buradaki `launch_widget.py`, `rctrl_widget.py` ve `core/` üzerinde çalışın. Dağıtım zip’lerini `dist/` altına koyabilirsiniz.

## Testler

```bash
python -m pytest              # hızlı suite (slow hariç)
set RCTRL_E2E=1
python -m pytest -m slow        # gerçek tiny Whisper + WAV hattı
```

Katkı rehberi: [CONTRIBUTING.tr.md](CONTRIBUTING.tr.md).

## Bilinen sınırlar / yol haritası

- Yapıştırma başarısız olursa metin panoda kalır; kapsül uyarı gösterir; geçmişe yazılır.
- Windows, yapıştırmanın hedef pencerede görünüp görünmediğini bildirmez — başarıda hedefi kontrol edin.
- **Dikte geçmişi** (sağ menü): satıra tıklayınca **yapıştırır**.
- **Dikte kutusu** (📥): satır seçince **panoya kopyalar**; toplu kopya tek satır sonu ile birleşir.
- Sunucu `/dictate` kayıtları menü veya kutu açılırken `inbox.json`'dan yenilenir.
- Geniş entegrasyon: `RCTRL_E2E=1 pytest -m slow`.
- Sunum `rctrl_widget.py`; mantık `rctrl_controller.py`.
- Yalnızca Windows.

## Lisans

MIT — bkz. [LICENSE](LICENSE).
