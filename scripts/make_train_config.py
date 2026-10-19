"""Materialize a portable OneTrainer template; this command never starts training."""
import argparse
import copy
import json
from pathlib import Path
import shutil

from project_paths import ROOT, expand_template, path_for


def build(template: dict, base: Path, dataset: Path, run: Path, output: Path) -> dict:
    variables = {"PROJECT_ROOT": str(ROOT), "BASE_MODEL": str(base), "DATASET_DIR": str(dataset),
                 "RUN_DIR": str(run), "OUTPUT_MODEL": str(output), "CONCEPTS_FILE": str(run / "concepts.json")}
    return expand_template(copy.deepcopy(template), variables)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--local-config", type=Path)
    parser.add_argument("--template", type=Path, default=ROOT / "configs/train_v6.example.json")
    parser.add_argument("--run-dir", type=Path)
    parser.add_argument("--smoke-images", type=int, help="Copy N labeled images into a new run; one epoch, one repeat")
    args = parser.parse_args()
    dataset = path_for("dataset", args.local_config)
    base = path_for("base_model", args.local_config)
    run = args.run_dir.resolve() if args.run_dir else path_for("run", args.local_config)
    output = path_for("output_model", args.local_config)
    if not dataset.is_dir() or not base.is_file():
        parser.error("Set an existing dataset and base_model in local.toml; no assets are downloaded")
    if run.exists():
        parser.error("Use a new run directory; existing runs are preserved")
    if args.smoke_images is not None and args.smoke_images < 1:
        parser.error("--smoke-images must be positive")
    pairs = [(p, p.with_suffix(".txt")) for p in sorted(dataset.iterdir()) if p.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp", ".bmp"}]
    if not pairs or any(not text.is_file() for _, text in pairs):
        parser.error("Dataset must contain images with same-stem caption files")
    if output.exists() and args.smoke_images is None:
        parser.error("Output model already exists; choose a new filename")
    if args.smoke_images and len(pairs) < args.smoke_images:
        parser.error("Not enough labeled images for the requested smoke subset")
    run.mkdir(parents=True)
    if args.smoke_images:
        subset = run / "smoke_dataset"
        subset.mkdir()
        for image, caption in pairs[:args.smoke_images]:
            shutil.copy2(image, subset / image.name)
            shutil.copy2(caption, subset / caption.name)
        dataset = subset
        output = run / "smoke.safetensors"
    config = build(json.loads(args.template.read_text(encoding="utf-8")), base, dataset, run, output)
    if args.smoke_images:
        config.update(epochs=1, learning_rate_warmup_steps=0, samples=[], sample_after_unit="NEVER", save_every_unit="NEVER")
        for concept in config["concepts"]:
            concept["balancing"] = 1.0
    for name, value in [("train_config.json", config), ("concepts.json", config["concepts"]), ("samples.json", config.get("samples", []))]:
        (run / name).write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"config": str(run / "train_config.json"), "images": args.smoke_images or len(pairs),
                      "epochs": config["epochs"], "output_model": str(output), "training_started": False}, ensure_ascii=False))


if __name__ == "__main__":
    main()
