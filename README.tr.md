**Dil / Language:** [English](README.md) · **Türkçe**

# R-Ctrl — Whisperer (local)

**R-Ctrl — Whisperer**, yerel Windows diktesidir: kısayolu basılı tutun, konuşun, makinede **Whisper** (faster-whisper) ile metne çevirin, odaktaki uygulamaya **yapıştırın**. Varsayılan kısayol: **Sağ Ctrl** (`R-Ctrl`). Ses cihazdan çıkmaz; widget için API anahtarı gerekmez.

### Windows uygulaması (Python yok)

[GitHub Releases](https://github.com/polyfoil/R-Ctrl/releases) → `R-Ctrl-Whisperer-win64.zip`, **`Start-R-Ctrl-Whisperer.bat`** (UAC). İlk açılışta model iner (~3 GB). **CUDA Toolkit gerekmez.**

## Gereksinimler

- **Windows 10/11**
- **Zip kullanıcısı:** ilk çalıştırmada internet; global kısayol için UAC
- **Geliştirici:** Python 3.11+; `scripts\Widget.bat` (ilk seferde bağımlılık kurar, UAC)

## Hızlı başlangıç

| Mod | Çalıştır |
|-----|----------|
| **Widget** (ana) | `scripts\Widget.bat` → UAC → **R-Ctrl · Hazır** |
| **Sunucu** (tarayıcı) | `scripts\Server.bat` → http://127.0.0.1:5000 |

- **Sağ Ctrl** basılı = konuş; kısa dokunuş = toggle
- Kapsül **tık** = kayıt; **sağ tık** = model, mikrofon, dil, geçmiş
- **Tepsi** = göster/gizle, menü

### Giriş noktaları (geliştirici)

| Kullan | Kullanma |
|--------|----------|
| `python -m rctrl.launch` veya `scripts\Widget.bat` | `python -m rctrl.widget` (Qt, CUDA’dan önce) |
| `python -m rctrl.server` veya `scripts\Server.bat` | Sunucuyu auth/TLS olmadan `0.0.0.0`’a bağlamak |

### Model önbelleği

```text
%USERPROFILE%\.cache\huggingface\hub
```

## Release zip

1. Releases → zip indir, aç, **`Start-R-Ctrl-Whisperer.bat`**
2. `config.json` / `inbox.json` exe yanında; günlük: `%LOCALAPPDATA%\R-Ctrl\widget.log`

GPU sorunu: `config.json` içinde `"device": "cpu"`, `"model": "small"`, `"compute": "int8"` veya dosyayı silip yeniden başlatın.

## Kaynak koddan kurulum

```bash
git clone <repo-url>
cd R-Ctrl
scripts\Widget.bat
```

```bash
python -m pip install -r requirements-dev.txt
python -m pytest
python -m ruff check .
python -m mypy
```

Sunucu **127.0.0.1**; inbox’a kayıt var, tuş enjeksiyonu yok.

## Proje yapısı

| Yol | Rol |
|-----|-----|
| `core/` | Ses, motor, config, inject, geçmiş |
| `rctrl/` | Uygulama: `launch`, `widget`, `controller`, `inbox`, `server` |
| `ui/` | Marka ve i18n |
| `scripts/` | `Widget.bat`, `Server.bat` |
| `tests/` | Testler |
| `packaging/` | PyInstaller, `build_widget.ps1` |

`R-Ctrl-Widget/` klasörünü düzenlemeyin (eski zip kopyası, gitignore).

## Katkı

1. Widget: `scripts\Widget.bat` veya `python -m rctrl.launch`.
2. Değiştirdiğiniz mantık için test; `pytest`, `ruff`, `mypy`.
3. `config.json`, `inbox.json`, `.pm/`, `Docs/`, zip commit etmeyin.
4. Yapıştırma yalnızca `core.inject.paste_text()`; sunucu localhost dışına çıkmaz (auth+TLS olmadan).

## Bilinen sınırlar

- Yapıştırma Windows’ta doğrulanamaz; hata durumunda pano.
- Geçmiş satırı → yapıştır; inbox (📥) → kopyala.
- Yalnızca Windows.

## Lisans

MIT — [LICENSE](LICENSE).
