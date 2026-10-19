"""Create/reuse a Python 3.12 helper venv, preserve local configuration, verify it.

Installs only requirements.txt. Never installs GPU runtimes, downloads models,
starts services or trains. Run from any working directory.
"""
import argparse
from pathlib import Path
import subprocess
import sys
import venv

ROOT = Path(__file__).resolve().parents[1]


def initialize_config(root=ROOT):
    target = root / "configs/local.toml"
    try:
        with target.open("x", encoding="utf-8", newline="\n") as stream:
            stream.write((root / "configs/local.example.toml").read_text(encoding="utf-8"))
        return True
    except FileExistsError:
        return False


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-dir", type=Path, default=Path(".venv"), help="Relative to the repository root")
    parser.add_argument("--skip-install", action="store_true", help="Offline verification of an already-installed helper environment")
    args = parser.parse_args()
    if sys.version_info[:2] != (3, 12):
        parser.error("Use Python 3.12, including from Anaconda; no system Python will be installed")
    target = args.env_dir if args.env_dir.is_absolute() else ROOT / args.env_dir
    target = target.resolve()
    python = target / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")
    if target.exists():
        if not (target / "pyvenv.cfg").is_file() or not python.is_file():
            parser.error("Environment directory exists but is not a helper venv; choose a new directory")
        version = subprocess.check_output([str(python), "-c", "import sys; print('%d.%d' % sys.version_info[:2])"], text=True).strip()
        if version != "3.12":
            parser.error("Existing venv is not Python 3.12; choose a new directory")
    elif args.skip_install:
        parser.error("--skip-install requires an existing installed environment")
    else:
        venv.EnvBuilder(with_pip=True).create(target)
    def run(*command):
        subprocess.run([str(python), "-X", "utf8", *command], cwd=ROOT, check=True)
    if not args.skip_install:
        run("-m", "pip", "install", "-r", str(ROOT / "requirements.txt"))
    print("Local configuration created" if initialize_config() else "Existing local configuration preserved", flush=True)
    run(str(ROOT / "scripts/doctor.py"), "--profile", "helper")
    run("-m", "unittest", "discover", "-s", "tests", "-v")
    print(f"Helper environment ready: {python}\nEdit configs/local.toml before training or evaluation.")


if __name__ == "__main__":
    main()
