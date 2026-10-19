"""Portable configuration shared by the command line helpers (Python 3.12+)."""
from __future__ import annotations

import os
from pathlib import Path
import tomllib
from urllib.parse import urlsplit

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
    if not file.exists():
        if config is not None:
            raise FileNotFoundError(f"Explicit configuration does not exist: {file}")
        return {}
    value = tomllib.loads(file.read_text(encoding="utf-8"))
    allowed = {"paths": set(DEFAULTS), "comfyui": {"url"}}
    for table, entries in value.items():
        if table not in allowed or not isinstance(entries, dict):
            raise ValueError(f"Unknown configuration table: {table}")
        for key, item in entries.items():
            if key not in allowed[table]:
                raise ValueError(f"Unknown configuration key: {table}.{key}")
            if not isinstance(item, str) or not item.strip():
                raise ValueError(f"Expected a nonempty string: {table}.{key}")
    if "url" in value.get("comfyui", {}):
        validate_url(value["comfyui"]["url"])
    return value


def validate_url(url: str) -> str:
    parts = urlsplit(url)
    if parts.scheme not in {"http", "https"} or not parts.hostname or parts.username or parts.password or parts.query or parts.fragment:
        raise ValueError("ComfyUI URL must be HTTP(S), without credentials, query or fragment")
    return url.rstrip("/")


def path_for(name: str, config: Path | None = None) -> Path:
    value = os.environ.get(f"OC_{name.upper()}", settings(config).get("paths", {}).get(name, DEFAULTS[name]))
    path = Path(os.path.expandvars(value)).expanduser()
    return (path if path.is_absolute() else ROOT / path).resolve()


def comfy_url(config: Path | None = None) -> str:
    return validate_url(os.environ.get("OC_COMFYUI_URL", settings(config).get("comfyui", {}).get("url", "http://127.0.0.1:8188")))


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
