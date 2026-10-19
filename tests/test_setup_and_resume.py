"""CPU regressions for safe onboarding and evaluation provenance; no private assets."""
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from bootstrap import initialize_config
from doctor import check, probe_cuda
from evaluation_cache import fingerprint, load_completed
from project_paths import settings, validate_url


class SetupAndResumeTest(unittest.TestCase):
    def test_configuration_creation_preserves_existing_machine_settings(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "configs").mkdir()
            (root / "configs/local.example.toml").write_text('[paths]\ndataset="example"\n', encoding="utf-8")
            self.assertTrue(initialize_config(root))
            local = root / "configs/local.toml"
            local.write_text('[paths]\ndataset="private"\n', encoding="utf-8")
            before = local.read_bytes()
            self.assertFalse(initialize_config(root))
            self.assertEqual(before, local.read_bytes())

    def test_explicit_missing_configuration_does_not_fall_back(self):
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaises(FileNotFoundError):
                settings(Path(temp) / "absent.toml")

    def test_configuration_rejects_typos_empty_paths_and_credentials(self):
        with tempfile.TemporaryDirectory() as temp:
            local = Path(temp) / "config.toml"
            for value in ('[path]\ndataset="data"', '[paths]\ndatset="data"', '[paths]\ndataset=""',
                          '[paths]\ndataset=42', '[comfyui]\nurl=' + json.dumps('https://' + 'user:pass' + '@example.com')):
                with self.subTest(value=value):
                    local.write_text(value, encoding="utf-8")
                    with self.assertRaises(ValueError):
                        settings(local)
            self.assertEqual(validate_url("http://127.0.0.1:8188/"), "http://127.0.0.1:8188")

    def test_helper_doctor_needs_no_gpu_assets_or_network(self):
        with tempfile.TemporaryDirectory() as temp:
            local = Path(temp) / "config.toml"
            local.write_text('[paths]\nbase_model="missing-model"\ndataset="missing-data"\n', encoding="utf-8")
            with patch("doctor.probe_cuda", side_effect=AssertionError("No GPU probe in helper")), \
                 patch("doctor.urllib.request.urlopen", side_effect=AssertionError("No network in helper")):
                result = check("helper", local)
            self.assertTrue(result["passed"], result)
            self.assertIn("SKIP", [c["status"] for c in result["checks"]])

    def test_training_doctor_reports_missing_assets_and_unavailable_cuda(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            local = root / "config.toml"
            local.write_text('[paths]\n' + '\n'.join(key + '=' + json.dumps(str(root / key)) for key in
                             ("onetrainer", "base_model", "dataset", "run", "output_model")), encoding="utf-8")
            with patch.dict(os.environ, {k: v for k, v in os.environ.items() if not k.startswith("OC_")}, clear=True), \
                 patch("doctor.probe_cuda", return_value={"available": False}) as probe:
                result = check("training", local, Path("chosen-python"))
            probe.assert_called_once_with(Path("chosen-python"))
            failures = {c["name"] for c in result["checks"] if c["status"] == "FAIL"}
            self.assertTrue({"onetrainer", "base_model", "dataset", "training_cuda"}.issubset(failures))
            self.assertFalse(result["passed"])

    def test_cuda_probe_uses_selected_interpreter_and_times_out(self):
        data = subprocess.CompletedProcess([], 0, 'noise\nOC_DOCTOR_JSON={"available":true,"operator_ok":true}\n', '')
        with patch("doctor.subprocess.run", return_value=data) as run:
            self.assertTrue(probe_cuda("training-python")["operator_ok"])
        self.assertEqual(run.call_args.args[0][0], "training-python")
        self.assertEqual(run.call_args.kwargs["timeout"], 60)

    def test_comfy_doctor_only_reads_existing_server_and_reports_busy_queue(self):
        with tempfile.TemporaryDirectory() as temp:
            config = Path(temp) / "local.toml"
            config.write_text('[paths]\nbase_model="models/base.safetensors"\n', encoding="utf-8")
            responses = [io.BytesIO(json.dumps({"queue_running": [[1]], "queue_pending": []}).encode()),
                         io.BytesIO(json.dumps({"CheckpointLoaderSimple": {"input": {"required": {"ckpt_name": [["base.safetensors"]]}}}}).encode())]
            with patch.dict(os.environ, {k: v for k, v in os.environ.items() if not k.startswith("OC_")}, clear=True), \
                 patch("doctor.urllib.request.urlopen", side_effect=responses) as request:
                result = check("comfyui", config, url="http://127.0.0.1:8188")
            self.assertFalse(result["passed"])
            self.assertEqual([c.args[0].rsplit("/", 1)[-1] for c in request.call_args_list], ["queue", "object_info"])

    def completed(self, root, spec):
        (root / "images").mkdir()
        data = b"synthetic output bytes, not a private image"
        (root / "images" / (spec["name"] + ".png")).write_bytes(data)
        results = [{"name": spec["name"], "spec": spec, "graph_sha256": fingerprint(spec),
                    "image_sha256": hashlib.sha256(data).hexdigest()}]
        (root / "results.json").write_text(json.dumps(results), encoding="utf-8")
        return results

    def test_resume_keeps_identical_outputs_and_allows_new_jobs(self):
        spec = {"name": "one", "seed": 1, "prompt": "naikaer_oc, 1girl"}
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            results = self.completed(root, spec)
            self.assertEqual(load_completed(root, [spec, {"name": "two", "seed": 2}]), results)

    def test_resume_rejects_changed_generation_parameters_before_network(self):
        spec = {"name": "one", "seed": 1, "lora": "v6.safetensors", "strength": .7, "mode": "pixel_hires"}
        changes = {"seed": 2, "prompt": "changed", "negative": "changed", "checkpoint": "new.safetensors",
                   "strength": 1.0, "lora": "v5.safetensors", "width": 1024, "height": 1536,
                   "steps": 40, "cfg": 7, "sampler": "euler", "scheduler": "normal", "denoise": .5, "refine_steps": 30}
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.completed(root, spec)
            for key, value in changes.items():
                with self.subTest(key=key), self.assertRaises(ValueError):
                    load_completed(root, [dict(spec, **{key: value})])
            plan = root / "plan.json"
            plan.write_text(json.dumps([dict(spec, seed=2)]), encoding="utf-8")
            result = subprocess.run([sys.executable, str(ROOT / "scripts/comfy_evaluate.py"), "--plan", str(plan),
                                     "--output", str(root), "--resume", "--url", "http://127.0.0.1:1"], capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("Changed parameters", result.stderr)
            self.assertNotIn("Connection", result.stderr)

    def test_resume_rejects_legacy_missing_or_modified_images(self):
        spec = {"name": "one", "seed": 1}
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            results = self.completed(root, spec)
            image = root / "images/one.png"
            image.write_bytes(b"modified")
            with self.assertRaises(ValueError):
                load_completed(root, [spec])
            image.unlink()
            with self.assertRaises(ValueError):
                load_completed(root, [spec])
            results[0].pop("graph_sha256")
            (root / "results.json").write_text(json.dumps(results), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "legacy"):
                load_completed(root, [spec])

    def test_published_workflow_links_and_plan_graphs_are_consistent(self):
        for file in (ROOT / "workflows").glob("*.json"):
            workflow = json.loads(file.read_text(encoding="utf-8"))
            nodes = {n["id"]: n for n in workflow["nodes"]}
            for link in workflow["links"]:
                link_id, source, source_slot, target, target_slot, kind = link
                self.assertIn(link_id, nodes[source]["outputs"][source_slot]["links"])
                self.assertEqual(nodes[target]["inputs"][target_slot]["link"], link_id)
        for file in (ROOT / "configs").glob("evaluation_*.example.json"):
            for spec in json.loads(file.read_text(encoding="utf-8")):
                self.assertEqual(len(fingerprint(spec)), 64)


if __name__ == "__main__":
    unittest.main()
