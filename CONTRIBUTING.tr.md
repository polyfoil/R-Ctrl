**Dil / Language:** [English](CONTRIBUTING.md) · **Türkçe**

# Katkıda bulunma

1. Widget geliştirmede Windows’ta `launch_widget.py` / `rctrl_widget.bat` kullanın (Qt’den önce CUDA).
2. Dokunduğunuz mantık için test ekleyin veya güncelleyin; `python -m pytest`, `python -m ruff check .`, `python -m mypy` çalıştırın.
3. `config.json`, `inbox.json`, model önbelleği, `.pm/`, `Docs/` ve `dist/` altındaki zip’leri commit etmeyin.
4. `R-Ctrl-Widget/` düzenlemeyin — gitignore’daki eski kopya; yalnızca repo kökündeki kaynaklar.

### Davranış kuralları (özet)

- Uygulamalara metin: yalnızca `core.inject.paste_text()` (pano); `keyboard.write()` kullanmayın.
- Ses: 16 kHz mono float32 bellek içi; yerel Whisper için geçici WAV yok.
- Sunucu `127.0.0.1`’de kalmalı; auth + TLS olmadan açmayın.

Pull request’ler memnuniyetle karşılanır; büyük özellikler için önce issue açın.

Belgeler: [README.tr.md](README.tr.md) (Türkçe), [README.md](README.md) (English).
