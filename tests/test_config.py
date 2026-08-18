"""Tests for core.config — hardware detection and settings persistence."""

import json

import pytest

from core import config as cfg

# --- compute_for_device ---------------------------------------------------

def test_cuda_uses_float16():
    assert cfg.compute_for_device("cuda") == "float16"


def test_cpu_uses_int8():
    assert cfg.compute_for_device("cpu") == "int8"


# --- detect_hardware ------------------------------------------------------

def _fake_probe(
    monkeypatch,
    *,
    cuda_devices: int,
    vram_mb: int = 0,
    name: str = "Fake GPU",
    smi_ok: bool = True,
):
    """Force detect_hardware down a specific branch (ctranslate2 + optional nvidia-smi)."""

    class _FakeCT2:
        @staticmethod
        def get_cuda_device_count() -> int:
            return cuda_devices

    monkeypatch.setitem(__import__("sys").modules, "ctranslate2", _FakeCT2)

    if smi_ok and vram_mb > 0:
        payload = f"{name}, {vram_mb}\n"
        monkeypatch.setattr(cfg.subprocess, "check_output", lambda *a, **k: payload)
    else:
        def _boom(*a, **k):
            raise FileNotFoundError("nvidia-smi not found")

        monkeypatch.setattr(cfg.subprocess, "check_output", _boom)


def test_large_gpu_selects_large_v3(monkeypatch):
    _fake_probe(monkeypatch, cuda_devices=1, vram_mb=12000)
    hw = cfg.detect_hardware()
    assert (hw["model"], hw["device"], hw["compute"]) == ("large-v3", "cuda", "float16")


def test_vram_exactly_at_large_threshold_selects_large(monkeypatch):
    _fake_probe(monkeypatch, cuda_devices=1, vram_mb=cfg.VRAM_LARGE_MB)
    assert cfg.detect_hardware()["model"] == "large-v3"


def test_just_below_large_threshold_selects_medium(monkeypatch):
    _fake_probe(monkeypatch, cuda_devices=1, vram_mb=cfg.VRAM_LARGE_MB - 1)
    assert cfg.detect_hardware()["model"] == "medium"


def test_vram_exactly_at_medium_threshold_selects_medium(monkeypatch):
    _fake_probe(monkeypatch, cuda_devices=1, vram_mb=cfg.VRAM_MEDIUM_MB)
    assert cfg.detect_hardware()["model"] == "medium"


def test_low_vram_gpu_selects_small(monkeypatch):
    _fake_probe(monkeypatch, cuda_devices=1, vram_mb=2000)
    hw = cfg.detect_hardware()
    assert hw["model"] == "small"
    assert hw["device"] == "cuda"


def test_no_gpu_falls_back_to_cpu_int8(monkeypatch):
    _fake_probe(monkeypatch, cuda_devices=0, smi_ok=False)
    hw = cfg.detect_hardware()
    assert (hw["model"], hw["device"], hw["compute"]) == ("small", "cpu", "int8")
    assert hw["cuda_available"] is False


def test_nvidia_smi_without_cuda_runtime_selects_cpu(monkeypatch):
    """Driver may report a GPU while ctranslate2 cannot use CUDA (no Toolkit needed)."""
    _fake_probe(monkeypatch, cuda_devices=0, vram_mb=12000)
    hw = cfg.detect_hardware()
    assert (hw["model"], hw["device"], hw["compute"]) == ("small", "cpu", "int8")
    assert hw["cuda_available"] is False
    assert hw["gpu_name"] == "Fake GPU"
    assert "CUDA inference is not available" in hw["reason"]


def test_cuda_without_smi_uses_small_on_gpu(monkeypatch):
    _fake_probe(monkeypatch, cuda_devices=1, smi_ok=False)
    hw = cfg.detect_hardware()
    assert hw["cuda_available"] is True
    assert (hw["model"], hw["device"]) == ("small", "cuda")
    assert hw["vram_mb"] == 0


def test_load_or_create_does_not_downgrade_cuda_alone(tmp_path, monkeypatch):
    _fake_probe(monkeypatch, cuda_devices=0, vram_mb=12000)
    path = tmp_path / "config.json"
    path.write_text(
        json.dumps({"model": "large-v3", "device": "cuda", "compute": "float16"}),
        encoding="utf-8",
    )
    conf, _ = cfg.load_or_create_config(path)
    assert conf["device"] == "cuda"


def test_sync_widget_downgrades_invalid_cuda(tmp_path, monkeypatch):
    _fake_probe(monkeypatch, cuda_devices=0, vram_mb=12000)
    path = tmp_path / "config.json"
    path.write_text(
        json.dumps({"model": "large-v3", "device": "cuda", "compute": "float16"}),
        encoding="utf-8",
    )
    conf, hw = cfg.load_or_create_config(path)
    conf = cfg.sync_widget_device_with_hardware(conf, hw, path)
    assert conf["device"] == "cpu"
    assert conf["model"] == "small"
    assert conf[cfg.GPU_AUTO_FALLBACK_KEY] is True
    on_disk = json.loads(path.read_text(encoding="utf-8"))
    assert on_disk["device"] == "cpu"


def test_sync_restores_gpu_after_cuda_returns(tmp_path, monkeypatch):
    path = tmp_path / "config.json"
    path.write_text(
        json.dumps(
            {
                "model": "small",
                "device": "cpu",
                "compute": "int8",
                cfg.GPU_AUTO_FALLBACK_KEY: True,
            }
        ),
        encoding="utf-8",
    )
    _fake_probe(monkeypatch, cuda_devices=1, vram_mb=12000)
    hw = cfg.detect_hardware()
    conf = {"model": "small", "device": "cpu", "compute": "int8", cfg.GPU_AUTO_FALLBACK_KEY: True}
    conf = cfg.sync_widget_device_with_hardware(conf, hw, path)
    assert conf["device"] == "cuda"
    assert conf["model"] == "large-v3"
    assert cfg.GPU_AUTO_FALLBACK_KEY not in conf


def test_detect_hardware_always_reports_a_reason(monkeypatch):
    _fake_probe(monkeypatch, cuda_devices=1, vram_mb=12000)
    assert cfg.detect_hardware()["reason"]


# --- probe noise ----------------------------------------------------------
#
# "Never swallow exceptions silently" is a rule about *unexpected* failures.
# On a machine with no NVIDIA GPU both probes always fail, so logging them
# turned normal operation into two error lines on every single launch.

def test_absent_gpu_produces_no_error_output(monkeypatch, capsys):
    _fake_probe(monkeypatch, cuda_devices=0, smi_ok=False)
    cfg.detect_hardware()
    out = capsys.readouterr()
    assert out.out == "", f"a GPU-less machine must start quietly, got: {out.out!r}"
    assert out.err == ""


def test_absent_gpu_still_explains_itself_in_the_result(monkeypatch):
    """Quiet does not mean uninformative — the reason field carries the news."""
    _fake_probe(monkeypatch, cuda_devices=0, smi_ok=False)
    hw = cfg.detect_hardware()
    assert "No NVIDIA GPU" in hw["reason"]
    assert hw["cuda_available"] is False


def test_probe_results_are_reported_structurally(monkeypatch):
    """Callers must be able to inspect what happened without parsing logs."""
    _fake_probe(monkeypatch, cuda_devices=0, smi_ok=False)
    hw = cfg.detect_hardware()
    assert "probes" in hw, "detect_hardware should expose per-probe outcomes"
    assert hw["probes"]["nvidia_smi"]["ok"] is False
    assert hw["probes"]["nvidia_smi"]["detail"]



def test_config_load_is_quiet_on_a_healthy_path(tmp_path, stub_hardware, capsys):
    cfg.load_or_create_config(tmp_path / "config.json")
    assert capsys.readouterr().out == ""


def test_corrupt_config_does_log(tmp_path, stub_hardware, capsys):
    """A genuinely unexpected failure must still be reported."""
    path = tmp_path / "config.json"
    path.write_text("{ not json", encoding="utf-8")
    cfg.load_or_create_config(path)
    assert "config.json" in capsys.readouterr().out


# --- load_or_create_config ------------------------------------------------

@pytest.fixture
def stub_hardware(monkeypatch):
    monkeypatch.setattr(cfg, "detect_hardware", lambda: {
        "gpu_name": "Fake GPU", "vram_mb": 12000, "cuda_available": True,
        "model": "large-v3", "device": "cuda", "compute": "float16",
        "reason": "stub",
    })


def test_creates_file_when_missing(tmp_path, stub_hardware, monkeypatch):
    monkeypatch.setattr(cfg, "detect_system_ui_language", lambda: "tr")
    path = tmp_path / "config.json"
    conf, hw = cfg.load_or_create_config(path)
    assert path.exists()
    assert conf["model"] == "large-v3"
    assert conf["ui_language"] == "tr"
    assert conf["language"] is None
    assert hw["reason"] == "stub"


def test_first_run_voice_auto_persisted_on_disk(tmp_path, stub_hardware, monkeypatch):
    monkeypatch.setattr(cfg, "detect_system_ui_language", lambda: "en")
    path = tmp_path / "config.json"
    cfg.load_or_create_config(path)
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["ui_language"] == "en"
    assert data["language"] is None


def test_user_language_settings_survive_reload(tmp_path, stub_hardware, monkeypatch):
    monkeypatch.setattr(cfg, "detect_system_ui_language", lambda: "tr")
    path = tmp_path / "config.json"
    cfg.load_or_create_config(path)
    cfg.save_config(
        {
            "model": "medium",
            "device": "cuda",
            "compute": "float16",
            "hotkey": "f12",
            "language": "en",
            "ui_language": "en",
            "input_device": 2,
        },
        path,
    )
    conf, _ = cfg.load_or_create_config(path)
    assert conf["model"] == "medium"
    assert conf["hotkey"] == "f12"
    assert conf["language"] == "en"
    assert conf["ui_language"] == "en"
    assert conf["input_device"] == 2


def test_detect_system_ui_language_turkish_locale(monkeypatch):
    monkeypatch.setattr(cfg.sys, "platform", "linux")
    monkeypatch.setattr(cfg.locale, "getlocale", lambda *a, **k: ("tr_TR", "UTF-8"))
    assert cfg.detect_system_ui_language() == "tr"


def test_detect_system_ui_language_defaults_to_en(monkeypatch):
    monkeypatch.setattr(cfg.sys, "platform", "linux")
    monkeypatch.setattr(cfg.locale, "getlocale", lambda *a, **k: (None, None))
    assert cfg.detect_system_ui_language() == "en"


def test_returns_a_two_tuple(tmp_path, stub_hardware):
    # The old annotation claimed `-> dict` while returning a tuple.
    result = cfg.load_or_create_config(tmp_path / "config.json")
    assert isinstance(result, tuple) and len(result) == 2


def test_saved_values_override_detected_defaults(tmp_path, stub_hardware):
    path = tmp_path / "config.json"
    path.write_text(json.dumps({"model": "base", "hotkey": "f12"}), encoding="utf-8")
    conf, _ = cfg.load_or_create_config(path)
    assert conf["model"] == "base"
    assert conf["hotkey"] == "f12"


def test_missing_keys_fall_back_to_defaults(tmp_path, stub_hardware):
    path = tmp_path / "config.json"
    path.write_text(json.dumps({"model": "base"}), encoding="utf-8")
    conf, _ = cfg.load_or_create_config(path)
    assert conf["ui_language"] == cfg.DEFAULT_CONFIG["ui_language"]
    assert conf["input_device"] is None


def test_corrupt_json_falls_back_to_defaults(tmp_path, stub_hardware):
    path = tmp_path / "config.json"
    path.write_text("{ this is not json", encoding="utf-8")
    conf, _ = cfg.load_or_create_config(path)
    assert conf["model"] == "large-v3"


def test_save_config_round_trips_unicode(tmp_path):
    path = tmp_path / "config.json"
    cfg.save_config({"note": "Türkçe ığşçöü"}, path)
    assert json.loads(path.read_text(encoding="utf-8"))["note"] == "Türkçe ığşçöü"


def test_app_root_uses_exe_parent_when_frozen(monkeypatch, tmp_path):
    fake_exe = tmp_path / "bin" / "R-Ctrl-Whisperer.exe"
    fake_exe.parent.mkdir(parents=True)
    fake_exe.touch()
    monkeypatch.setattr(cfg.sys, "frozen", True, raising=False)
    monkeypatch.setattr(cfg.sys, "executable", str(fake_exe))
    assert cfg.app_root() == fake_exe.parent.resolve()
