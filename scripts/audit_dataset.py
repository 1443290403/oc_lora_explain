"""Read-only image/caption audit; metrics help triage and do not certify quality."""
import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageOps

EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}


def audit(dataset: Path) -> dict:
    rows, fingerprints = [], []
    for path in sorted(p for p in dataset.iterdir() if p.suffix.lower() in EXTENSIONS):
        row = {"name": path.name, "caption_present": path.with_suffix(".txt").is_file()}
        try:
            with Image.open(path) as source:
                source.load()
                image = ImageOps.exif_transpose(source).convert("RGB")
                rgb = np.asarray(image, dtype=np.float32) / 255
                gray = np.asarray(image.convert("L").resize((256, 256)), dtype=np.float32)
                small = np.asarray(image.convert("L").resize((32, 32)), dtype=np.float32)
                basis = np.cos(np.pi * np.arange(8)[:, None] * (np.arange(32)[None, :] + .5) / 32)
                dct = basis @ small @ basis.T
                fingerprints.append((path.name, (dct > np.median(dct.flatten()[1:])).flatten()))
                lap = gray[1:-1, :-2] + gray[1:-1, 2:] + gray[:-2, 1:-1] + gray[2:, 1:-1] - 4 * gray[1:-1, 1:-1]
                row.update(width=image.width, height=image.height,
                           sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                           laplacian_variance=round(float(lap.var()), 3),
                           mean_luma=float((rgb @ np.array([.2126, .7152, .0722])).mean()),
                           near_white_pct=float((rgb.min(2) >= 250 / 255).mean() * 100))
        except Exception as exc:
            row["error"] = str(exc)
        rows.append(row)
    near = []
    for index, (name, bits) in enumerate(fingerprints):
        for other, second in fingerprints[index + 1:]:
            distance = int(np.count_nonzero(bits != second))
            if distance <= 8:
                near.append({"names": [name, other], "phash_distance": distance})
    return {"images": rows, "near_duplicates": near,
            "limitations": "Whole-image whites include clothing/background; blur and pHash are triage hints, not quality or identity judgments."}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("dataset", type=Path)
    parser.add_argument("--output", type=Path, required=True, help="Private runtime JSON, e.g. runs/audit.json")
    args = parser.parse_args()
    if not args.dataset.is_dir():
        parser.error("Dataset directory does not exist")
    if args.output.exists():
        parser.error("Refusing to overwrite an existing audit")
    result = audit(args.dataset)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"images": len(result["images"]), "errors": sum("error" in r for r in result["images"]),
                      "missing_captions": sum(not r["caption_present"] for r in result["images"]),
                      "output": str(args.output)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
