"""Resume only completed images from the same effective graph; never guess legacy provenance."""
import hashlib
import json

from comfy_graph import graph


def fingerprint(spec):
    payload = json.dumps(graph(spec), sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def load_completed(output, plan):
    result_file = output / "results.json"
    if not result_file.exists():
        return []
    results = json.loads(result_file.read_text(encoding="utf-8"))
    if not isinstance(results, list):
        raise ValueError("Invalid results.json; choose a new output directory")
    planned = {spec["name"]: spec for spec in plan}
    seen = set()
    for row in results:
        name = row.get("name") if isinstance(row, dict) else None
        if name not in planned or name in seen:
            raise ValueError("Completed names differ from the plan; choose a new output directory")
        seen.add(name)
        if row.get("graph_sha256") != fingerprint(planned[name]):
            raise ValueError(f"Changed parameters or legacy result: {name}; choose a new output directory")
        image = output / "images" / (name + ".png")
        if not image.is_file() or row.get("image_sha256") != hashlib.sha256(image.read_bytes()).hexdigest():
            raise ValueError(f"Missing or changed completed image: {name}; choose a new output directory")
    return results
