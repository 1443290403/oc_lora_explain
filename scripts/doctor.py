"""Read-only preflight. Helper works without models, GPU, OneTrainer or ComfyUI.

Training checks use --training-python, never the helper environment's Torch.
ComfyUI checks only query an existing server; no queue or process is changed.
"""
import argparse
import importlib
import importlib.metadata
import json
from pathlib import Path
import shutil
import subprocess
import sys
import urllib.request

from project_paths import ROOT, comfy_url, path_for, settings

PACKAGES = {"numpy": "numpy", "Pillow": "PIL.Image", "psutil": "psutil", "safetensors": "safetensors"}
CUDA_PROBE = """
import json, torch
available = torch.cuda.is_available()
data = {"torch": torch.__version__, "cuda": torch.version.cuda, "available": available}
if available:
    x = torch.ones(4, device="cuda")
    data.update(gpu=torch.cuda.get_device_name(0), vram_mib=torch.cuda.get_device_properties(0).total_memory // 1048576,
                operator_ok=float((x * 2).sum().item()) == 8.0)
print("OC_DOCTOR_JSON=" + json.dumps(data))
"""


def probe_cuda(python):
    result = subprocess.run([str(python), "-X", "utf8", "-c", CUDA_PROBE], capture_output=True, text=True,
                            encoding="utf-8", errors="replace", timeout=60)
    rows = [row.removeprefix("OC_DOCTOR_JSON=") for row in result.stdout.splitlines() if row.startswith("OC_DOCTOR_JSON=")]
    if result.returncode or not rows:
        raise RuntimeError("Torch/CUDA probe failed in the selected training interpreter; check its Torch install and driver")
    return json.loads(rows[-1])


def check(profile="helper", config=None, training_python=None, url=None):
    checks = []
    def add(name, status, detail):
        checks.append({"name": name, "status": status, "detail": detail})
    add("python", "PASS" if sys.version_info[:2] == (3, 12) else "FAIL", "Python " + sys.version.split()[0] + "; required 3.12")
    pins = dict(line.strip().split("==") for line in (ROOT / "requirements.txt").read_text().splitlines()
                if line.strip() and not line.startswith("#"))
    for package, module in PACKAGES.items():
        try:
            version = importlib.metadata.version(package)
            importlib.import_module(module)
            add(package, "PASS" if version == pins[package] else "FAIL", f"{version}; required {pins[package]}")
        except Exception as error:
            add(package, "FAIL", "Cannot import dependency: " + type(error).__name__ + "; rerun setup")
    try:
        settings(config)
        configured = config is not None or (ROOT / "configs/local.toml").is_file()
        add("configuration", "PASS" if configured else "WARN", "Validated local settings" if configured else "Using defaults; setup creates configs/local.toml")
    except (ValueError, OSError) as error:
        add("configuration", "FAIL", str(error))
        return {"profile": profile, "passed": False, "checks": checks}
    free_gib = round(shutil.disk_usage(ROOT).free / 1024 ** 3, 2)
    add("disk", "WARN" if free_gib < 10 else "PASS", f"{free_gib} GiB free on repository volume; model/cache volumes may differ")
    if profile == "helper":
        add("gpu_and_assets", "SKIP", "Helper mode needs no GPU, models, dataset or running services")
    if profile == "training":
        source = path_for("onetrainer", config)
        source_ok = (source / "modules").is_dir() and (source / "modules/util/config/TrainConfig.py").is_file()
        add("onetrainer", "PASS" if source_ok else "FAIL", str(source))
        if source_ok:
            try:
                commit = subprocess.check_output(["git", "-C", str(source), "rev-parse", "HEAD"], text=True, stderr=subprocess.DEVNULL, timeout=10).strip()
                tested = json.loads((ROOT / "env/tested_versions.json").read_text(encoding="utf-8"))["onetrainer"]["commit"]
                add("onetrainer_version", "PASS" if commit == tested else "WARN", commit + "; compare env/tested_versions.json before using the template")
            except (OSError, subprocess.SubprocessError):
                add("onetrainer_version", "WARN", "Cannot read source commit; configuration compatibility is unverified")
        model = path_for("base_model", config)
        add("base_model", "PASS" if model.is_file() and model.stat().st_size else "FAIL", str(model))
        dataset = path_for("dataset", config)
        pairs = [p for p in sorted(dataset.iterdir()) if p.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp", ".bmp"}] if dataset.is_dir() else []
        bad = 0
        for image in pairs:
            try:
                if not image.with_suffix(".txt").read_text(encoding="utf-8").strip():
                    bad += 1
            except (OSError, UnicodeError):
                bad += 1
        add("dataset", "PASS" if pairs and not bad else "FAIL", f"{len(pairs)} images, {bad} missing/empty/invalid UTF-8 captions; run audit_dataset.py for image review")
        for name in ("run", "output_model"):
            target = path_for(name, config)
            add(name, "FAIL" if target.exists() else "PASS", str(target) + (" already exists; choose a new destination" if target.exists() else " is unused"))
        if training_python is None:
            add("training_cuda", "FAIL", "Pass --training-python with the OneTrainer environment's Python executable")
        else:
            try:
                cuda = probe_cuda(training_python)
                add("training_cuda", "PASS" if cuda.get("available") and cuda.get("operator_ok") else "FAIL", json.dumps(cuda, ensure_ascii=False))
            except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
                add("training_cuda", "FAIL", str(error))
        add("training_scope", "WARN", "Preflight checks basic readiness only, not all OneTrainer dependencies or peak VRAM; validate a short run before full training")
    if profile == "comfyui":
        try:
            from project_paths import validate_url
            endpoint = validate_url(url) if url else comfy_url(config)
            def get(route):
                with urllib.request.urlopen(endpoint + route, timeout=10) as response:
                    return json.load(response)
            queue, objects = get("/queue"), get("/object_info")
            busy = bool(queue["queue_running"] or queue["queue_pending"])
            add("comfyui_queue", "FAIL" if busy else "PASS", "Busy; user jobs left untouched" if busy else "Connected and idle")
            checkpoint = path_for("base_model", config).name
            available = objects["CheckpointLoaderSimple"]["input"]["required"]["ckpt_name"][0]
            add("comfyui_checkpoint", "PASS" if checkpoint in available else "FAIL", checkpoint + "; plans may specify another installed name")
            add("comfyui_scope", "WARN", "Check each evaluation plan's LoRA names separately; no images were generated")
        except (OSError, ValueError, KeyError, TypeError) as error:
            add("comfyui", "FAIL", "Connection/API validation failed: " + type(error).__name__)
    return {"profile": profile, "passed": all(c["status"] != "FAIL" for c in checks), "checks": checks}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", choices=["helper", "training", "comfyui"], default="helper")
    parser.add_argument("--local-config", type=Path)
    parser.add_argument("--training-python", type=Path)
    parser.add_argument("--url")
    parser.add_argument("--json", action="store_true", help="Print machine-readable results")
    parser.add_argument("--output", type=Path, help="Save a private JSON report, preferably under runs/")
    args = parser.parse_args()
    result = check(args.profile, args.local_config, args.training_python, args.url)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        for row in result["checks"]:
            print(f"[{row['status']}] {row['name']}: {row['detail']}")
        print("READY" if result["passed"] else "NOT READY")
    raise SystemExit(0 if result["passed"] else 1)


if __name__ == "__main__":
    main()
