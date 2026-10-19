"""Portable configuration shared by the command line helpers (Python 3.12+)."""
from __future__ import annotations

import os
from pathlib import Path
import tomllib

ROOT = Path(__file__).resolve().parents[1]
DEFAULTS = {
    "onetrainer": "../OneTrainer", "comfyui": "../ComfyUI",
    "base_model": "models/waiIllustriousSDXL_v170.safetensors",
    "dataset": "data/clean_dataset_v6", "run": "runs/v6",
    "output_model": "outputs/naikaer_oc_v6.safetensors",
}


def settings(config: Path | None = None) -> dict:
    file = config or ROOT / "configs/local.toml"
    if not file.is_absolute():
        file = ROOT / file
    return tomllib.loads(file.read_text(encoding="utf-8")) if file.exists() else {}


def path_for(name: str, config: Path | None = None) -> Path:
    value = os.environ.get(f"OC_{name.upper()}", settings(config).get("paths", {}).get(name, DEFAULTS[name]))
    path = Path(os.path.expandvars(value)).expanduser()
    return (path if path.is_absolute() else ROOT / path).resolve()


def comfy_url(config: Path | None = None) -> str:
    return os.environ.get("OC_COMFYUI_URL", settings(config).get("comfyui", {}).get("url", "http://127.0.0.1:8188")).rstrip("/")


def expand_template(value, variables: dict[str, str]):
    """Expand only declared placeholders; reject forgotten variables."""
    if isinstance(value, dict):
        return {k: expand_template(v, variables) for k, v in value.items()}
    if isinstance(value, list):
        return [expand_template(v, variables) for v in value]
    if isinstance(value, str):
        for key, replacement in variables.items():
            value = value.replace("${" + key + "}", replacement)
        if "${" in value:
            raise ValueError(f"Unresolved template variable: {value}")
    return value
