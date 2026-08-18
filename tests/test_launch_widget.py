"""Smoke tests for launch_widget.py — model bootstrap before Qt."""

import pytest

import launch_widget as lw


class _FakeEngine:
    def __init__(self, **kwargs):
        self.model_size = kwargs.get("model_size", "small")
        self.device = kwargs.get("device", "cuda")
        self.load_calls = 0
        self.load_ok = True
        self.load_info = "small (cuda)"

    def load(self, log=None, **_kw):
        self.load_calls += 1
        if not self.load_ok:
            return False, "load failed"
        return True, self.load_info


def test_main_loads_engine_before_importing_widget(monkeypatch):
    created: list[_FakeEngine] = []
    run_args: list[tuple] = []

    def _factory(**kw):
        eng = _FakeEngine(**kw)
        created.append(eng)
        return eng

    monkeypatch.setattr(lw, "TranscriptionEngine", _factory)
    monkeypatch.setattr(lw, "load_or_create_config", lambda: ({"model": "small", "ui_language": "en"}, {"reason": "test"}))
    monkeypatch.setattr(lw, "sync_widget_device_with_hardware", lambda c, h: c)

    import rctrl_widget as widget

    monkeypatch.setattr(widget, "run_app", lambda config, hw, engine: run_args.append((config, hw, engine)))

    lw.main()

    assert len(created) == 1
    assert created[0].load_calls == 1
    assert len(run_args) == 1


def test_main_exits_when_model_load_fails(monkeypatch):
    monkeypatch.setattr(lw, "load_or_create_config", lambda: ({"model": "small", "ui_language": "en"}, {"reason": "test"}))
    monkeypatch.setattr(lw, "sync_widget_device_with_hardware", lambda c, h: c)
    engine = _FakeEngine()
    engine.load_ok = False
    monkeypatch.setattr(lw, "TranscriptionEngine", lambda **kw: engine)
    monkeypatch.setattr(lw, "fatal_widget_startup", lambda msg, **kw: (_ for _ in ()).throw(SystemExit(1)))

    with pytest.raises(SystemExit) as exc:
        lw.main()
    assert exc.value.code == 1
