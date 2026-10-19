"""Run a no-artist comparison plan against an already-running ComfyUI server."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import time
import urllib.parse
import urllib.request

from PIL import Image, ImageDraw, ImageFont
from comfy_graph import graph
from evaluation_cache import fingerprint, load_completed
from project_paths import comfy_url


class Client:
    def __init__(self, url):
        self.url = url.rstrip("/")

    def request(self, path, value=None):
        request = urllib.request.Request(self.url + path, data=None if value is None else json.dumps(value).encode(),
                                         headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(request, timeout=45) as response:
            data = response.read()
        return json.loads(data) if data else None

    def assert_idle(self):
        queue = self.request("/queue")
        if queue["queue_running"] or queue["queue_pending"]:
            raise RuntimeError("ComfyUI queue is busy; existing user jobs are left untouched")

    def run(self, prompt, timeout=600):
        self.assert_idle()
        pid = self.request("/prompt", {"prompt": prompt, "client_id": "oc-lora-comparison"})["prompt_id"]
        started = time.monotonic()
        while time.monotonic() - started < timeout:
            history = self.request("/history/" + pid)
            if pid in history:
                entry = history[pid]
                if entry["status"]["status_str"] != "success":
                    raise RuntimeError(f"ComfyUI execution failed; prompt_id={pid}")
                return pid, entry
            time.sleep(2)
        raise TimeoutError(f"Prompt did not finish; no interrupt was sent. prompt_id={pid}")

    def image(self, descriptor):
        query = urllib.parse.urlencode({k: descriptor[k] for k in ("filename", "subfolder", "type")})
        with urllib.request.urlopen(self.url + "/view?" + query, timeout=45) as response:
            return response.read()


def contact(results, output):
    width, height = 280, 450
    image = Image.new("RGB", (width * 4, height * ((len(results) + 3) // 4)), "#242833")
    draw, font = ImageDraw.Draw(image), ImageFont.load_default()
    for index, result in enumerate(results):
        with Image.open(output / "images" / (result["name"] + ".png")) as source:
            thumb = source.convert("RGB")
        thumb.thumbnail((width, height - 30))
        x, y = index % 4 * width, index // 4 * height
        image.paste(thumb, (x + (width - thumb.width) // 2, y))
        draw.text((x + 5, y + height - 25), result["name"], font=font, fill="white")
    image.save(output / "contact.jpg", quality=95)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True, help="Use a private ignored runtime directory under runs/")
    parser.add_argument("--url", default=comfy_url())
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--free-cache", action="store_true", help="Release cached models only if the queue is idle; never stops ComfyUI")
    args = parser.parse_args()
    plan = json.loads(args.plan.read_text(encoding="utf-8"))
    names = [s["name"] for s in plan]
    if not plan or len(set(names)) != len(names) or any(not re.fullmatch(r"[A-Za-z0-9_-]+", n) for n in names):
        parser.error("Plan needs unique ASCII names containing letters, digits, underscores or hyphens")
    if args.output.exists() and not args.resume:
        parser.error("Output exists; use a new directory or --resume")
    try:
        # Validate every existing result before making any server request.
        results = load_completed(args.output, plan) if args.resume else []
        for spec in plan:
            fingerprint(spec)
    except (ValueError, KeyError, AssertionError) as error:
        parser.error(str(error))
    client = Client(args.url)
    client.assert_idle()
    available = client.request("/object_info")
    for spec in plan:
        if spec.get("lora") and spec["lora"] not in available["LoraLoader"]["input"]["required"]["lora_name"][0]:
            parser.error(f"Install the planned LoRA or remove that baseline: {spec['lora']}")
    args.output.mkdir(parents=True, exist_ok=True)
    for directory in ("images", "api"):
        (args.output / directory).mkdir(exist_ok=True)
    result_file = args.output / "results.json"
    for spec in plan:
        if any(r["name"] == spec["name"] for r in results):
            continue
        prompt = graph(spec)
        api_file = args.output / "api" / (spec["name"] + ".json")
        api_file.write_text(json.dumps(prompt, ensure_ascii=False, indent=2), encoding="utf-8")
        print("START " + spec["name"], flush=True)
        started = time.monotonic()
        pid, history = client.run(prompt)
        (args.output / "api" / (spec["name"] + "_history.json")).write_text(json.dumps(history, ensure_ascii=False, indent=2), encoding="utf-8")
        target = args.output / "images" / (spec["name"] + ".png")
        target.write_bytes(client.image(history["outputs"]["8"]["images"][0]))
        results.append({"name": spec["name"], "spec": spec, "graph_sha256": fingerprint(spec),
                        "image_sha256": hashlib.sha256(target.read_bytes()).hexdigest(),
                        "prompt_id": pid, "seconds": round(time.monotonic() - started, 2)})
        temporary = result_file.with_suffix(".tmp")
        temporary.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
        temporary.replace(result_file)
        print("DONE " + spec["name"], flush=True)
    contact(results, args.output)
    if args.free_cache:
        client.assert_idle()
        client.request("/free", {"unload_models": True, "free_memory": True})


if __name__ == "__main__":
    main()
