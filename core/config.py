"""Hardware detection and persisted user settings."""

import json
import locale
import subprocess
import sys
from pathlib import Path


def app_root() -> Path:
    """Repo root in dev; folder containing the .exe when frozen (PyInstaller)."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


CONFIG_PATH = app_root() / "config.json"

# VRAM thresholds (MB) that decide which model a GPU can comfortably hold.
VRAM_LARGE_MB = 8000
VRAM_MEDIUM_MB = 4000

DEFAULT_CONFIG = {
    "model": "large-v3",
    "device": "cuda",
    "compute": "float16",
    "hotkey": "right ctrl",
    "language": None,
    "ui_language": "en",
    "input_device": None,
}


def detect_system_ui_language() -> str:
    """Map OS UI locale to a supported widget language code (tr | en)."""
    if sys.platform == "win32":
        try:
            import ctypes

            lang_id = ctypes.windll.kernel32.GetUserDefaultUILanguage()
            if (lang_id & 0x3FF) == 0x1F:
                return "tr"
        except Exception:
            pass
    for getter in (
        lambda: locale.getlocale(locale.LC_MESSAGES),
        locale.getlocale,
    ):
        try:
            loc = getter()
        except Exception:
            continue
        if not loc:
            continue
        tag = (loc[0] or "").lower()
        if tag.startswith("tr"):
            return "tr"
    return "en"


def _log(msg: str) -> None:
    print(f"[rctrl-config] {msg}", flush=True)


def detect_hardware() -> dict:
    """Probe for an NVIDIA GPU and pick a model that fits its VRAM.

    Probe failures are returned in the result rather than logged. On a machine
    without an NVIDIA GPU *both* probes always fail — that is the normal path,
    not an error, and logging it turned every launch into two scary-looking
    lines. The outcome still reaches the user through `reason`, and callers
    that want the detail can read `probes`.
    """
    gpu_name = None
    vram_mb = 0
    cuda_available = False
    probes: dict[str, dict] = {}

    try:
        import ctranslate2
        count = ctranslate2.get_cuda_device_count()
        cuda_available = count > 0
        probes["ctranslate2"] = {"ok": cuda_available, "detail": f"{count} CUDA device(s)"}
    except Exception as e:
        probes["ctranslate2"] = {"ok": False, "detail": str(e) or type(e).__name__}

    try:
        out = subprocess.check_output(
            ["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader,nounits"],
            text=True, stderr=subprocess.DEVNULL
        ).strip()
        if out:
            parts = out.split("\n")[0].split(",")
            gpu_name = parts[0].strip()
            vram_mb = int(parts[1].strip())
            cuda_available = True
        probes["nvidia_smi"] = {"ok": bool(out), "detail": out or "no output"}
    except Exception as e:
        probes["nvidia_smi"] = {"ok": False, "detail": str(e) or type(e).__name__}

    if cuda_available and vram_mb >= VRAM_LARGE_MB:
        model, device, compute = "large-v3", "cuda", "float16"
        reason = f"{gpu_name} ({vram_mb // 1024} GB VRAM) — 'large-v3' selected."
    elif cuda_available and vram_mb >= VRAM_MEDIUM_MB:
        model, device, compute = "medium", "cuda", "float16"
        reason = f"{gpu_name} ({vram_mb // 1024} GB VRAM) — 'medium' selected."
    elif cuda_available:
        model, device, compute = "small", "cuda", "float16"
        reason = f"{gpu_name} — 'small' selected."
    else:
        model, device, compute = "small", "cpu", "int8"
        reason = "No NVIDIA GPU detected. CPU selected with 'small (int8)'."

    return {
        "gpu_name": gpu_name,
        "vram_mb": vram_mb,
        "cuda_available": cuda_available,
        "model": model,
        "device": device,
        "compute": compute,
        "reason": reason,
        "probes": probes,
    }


def load_or_create_config(path: Path = CONFIG_PATH) -> tuple[dict, dict]:
    """Return (config, hardware_info), creating the file on first run.

    Detected hardware supplies the defaults; anything already saved wins, so a
    user's explicit model choice survives a restart.
    """
    cfg = dict(DEFAULT_CONFIG)
    hw = detect_hardware()
    cfg["model"] = hw["model"]
    cfg["device"] = hw["device"]
    cfg["compute"] = hw["compute"]

    if path.exists():
        try:
            with open(path, encoding="utf-8") as f:
                cfg.update(json.load(f))
        except Exception as e:
            _log(f"Could not read {path.name} ({e}) — falling back to defaults.")
    else:
        cfg["ui_language"] = detect_system_ui_language()
        cfg["language"] = None
        save_config(cfg, path)

    return cfg, hw


def save_config(cfg: dict, path: Path = CONFIG_PATH) -> None:
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2, ensure_ascii=False)
    except Exception as e:
        _log(f"Config save error: {e}")


def compute_for_device(device: str) -> str:
    """The compute type that matches a device — float16 needs a GPU."""
    return "float16" if device == "cuda" else "int8"
