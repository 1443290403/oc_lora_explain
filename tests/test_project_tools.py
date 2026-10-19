"""CPU checks for publication boundaries and portable helper behavior."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from audit_dataset import audit
from check_publish import inspect
from comfy_graph import graph
from make_train_config import build
from project_paths import expand_template, path_for


class ProjectToolsTest(unittest.TestCase):
    def test_paths_are_relative_to_project_not_cwd(self):
        with tempfile.TemporaryDirectory() as temp:
            config = Path(temp) / "local.toml"
            config.write_text('[paths]\ndataset = "relative-data"\n', encoding="utf-8")
            with patch.dict(os.environ, {"OC_DATASET": "another-relative-dir"}):
                self.assertEqual(path_for("dataset", config), (ROOT / "another-relative-dir").resolve())

    def test_expansion_rejects_unresolved_variable(self):
        self.assertEqual(expand_template({"a": ["${BASE}/x"]}, {"BASE": "models"}), {"a": ["models/x"]})
        with self.assertRaises(ValueError):
            expand_template("${UNSET}", {})

    def test_training_template_is_fresh_and_portable(self):
        raw = json.loads((ROOT / "configs/train_v6.example.json").read_text(encoding="utf-8"))
        self.assertNotIn("secrets", raw)
        self.assertNotIn("cloud", raw)
        cfg = build(raw, ROOT / "models/base.safetensors", ROOT / "data/example", ROOT / "runs/example", ROOT / "outputs/example.safetensors")
        self.assertFalse(cfg["continue_last_backup"])
        self.assertEqual(cfg["lora_model_name"], "")
        self.assertFalse(cfg["text_encoder"]["train"])
        self.assertFalse(cfg["text_encoder_2"]["train"])
        self.assertNotIn("${", json.dumps(cfg))

    def test_smoke_config_does_not_modify_source(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            data = root / "data"
            data.mkdir()
            image = data / "sample.png"
            Image.new("RGB", (64, 96), "purple").save(image)
            caption = image.with_suffix(".txt")
            caption.write_text("naikaer_oc, 1girl, solo", encoding="utf-8")
            before = hashlib.sha256(image.read_bytes()).hexdigest()
            model = root / "placeholder.safetensors"
            model.write_bytes(b"placeholder for config generation only")
            local = root / "local.toml"
            local.write_text("[paths]\n" + "\n".join(k + " = " + json.dumps(str(v)) for k, v in {"base_model": model, "dataset": data, "output_model": root / "output.safetensors"}.items()), encoding="utf-8")
            run = root / "smoke"
            command = [sys.executable, str(ROOT / "scripts/make_train_config.py"), "--local-config", str(local), "--run-dir", str(run), "--smoke-images", "1"]
            result = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            cfg = json.loads((run / "train_config.json").read_text(encoding="utf-8"))
            self.assertEqual(cfg["epochs"], 1)
            self.assertEqual(cfg["concepts"][0]["balancing"], 1)
            self.assertEqual(cfg["samples"], [])
            self.assertEqual(hashlib.sha256(image.read_bytes()).hexdigest(), before)
            self.assertTrue(caption.is_file())
            again = subprocess.run(command, capture_output=True, text=True)
            self.assertNotEqual(again.returncode, 0)

    def test_audit_flags_corruption_and_missing_caption_read_only(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            first = root / "one.png"
            Image.new("RGB", (64, 64), "green").save(first)
            (root / "two.png").write_bytes(first.read_bytes())
            (root / "one.txt").write_text("naikaer_oc", encoding="utf-8")
            (root / "bad.png").write_bytes(b"not an image")
            before = first.read_bytes()
            result = audit(root)
            self.assertEqual(len(result["images"]), 3)
            self.assertEqual(sum("error" in row for row in result["images"]), 1)
            self.assertEqual(sum(row["caption_present"] for row in result["images"]), 1)
            self.assertEqual(first.read_bytes(), before)

    def test_hires_graph_preserves_prompt_and_has_no_style_correction(self):
        prompt = "naikaer_oc, 1girl, solo, black dress, standing, full body,"
        g = graph({"name": "sample", "seed": 42, "lora": "naikaer_oc_v6.safetensors", "strength": .7, "mode": "pixel_hires", "prompt": prompt, "negative": "low quality"})
        self.assertEqual(g["3"]["inputs"]["text"], prompt)
        self.assertEqual(g["4"]["inputs"]["text"], "low quality")
        self.assertEqual(g["9"]["class_type"], "ImageScale")
        self.assertEqual(g["11"]["inputs"]["denoise"], .30)
        self.assertEqual(g["8"]["inputs"]["images"], ["12", 0])
        self.assertNotIn("RescaleCFG", [n["class_type"] for n in g.values()])

    def test_publication_guard_catches_credentials_without_values_in_report(self):
        value = "gh" + "p_" + "a" * 36
        findings = inspect("configs/example.json", json.dumps({"example": value}).encode())
        self.assertTrue(any("credential" in f for f in findings))
        self.assertNotIn(value, str(findings))
        self.assertTrue(any("populated secret field" in f for f in inspect("configs/example.json", b'{"api_key":"nonempty"}')))

    def test_publication_guard_catches_private_data_and_paths(self):
        self.assertTrue(inspect("outputs/model.safetensors", b"model"))
        self.assertTrue(inspect("configs/local.toml", b"local"))
        local_path = "Q:" + "/" + "private/file"
        self.assertTrue(any("absolute path" in f for f in inspect("docs/example.md", local_path.encode())))
        self.assertTrue(inspect("docs/example.md", b"x" * 500_001))
        self.assertEqual(inspect("docs/example.md", b"Relative path: runs/example"), [])
        self.assertEqual(inspect("docs/example.md", b"https://github.com/owner/repo and http://127.0.0.1:8188"), [])

    def test_training_help_does_not_import_gpu_runtime(self):
        result = subprocess.run([sys.executable, str(ROOT / "scripts/run_training.py"), "--help"], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("--onetrainer", result.stdout)


if __name__ == "__main__":
    unittest.main()
