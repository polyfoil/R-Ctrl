---
name: analiz2
description: >-
  Use when the user runs /analiz2 or wants a compact Turkish project assessment
  in a single markdown file (same scope as analiz, no multi-file split, no .pm
  mirror unless explicitly requested).
---

# Proje Analiz2 (tek belge)

`/analiz` ile aynı inceleme kapsamı; çıktı **tek dosyadır**.

## Hazırlık

1. `.pm/04_Execution/Anatomy.md` varsa oku.
2. `pyproject.toml`, `requirements*.txt`, paketler `core/`, `rctrl/`, `ui/`.
3. Test sayısı: `python -m pytest -q`.

## Rapor

Tek dosya: `Docs/YYYY-MM-DD_HHMM_analizi2.md` — 13 kategori, tablolar, puanlar, kod snippet yok.

Varsayılan: `.pm` güncelleme yok.
