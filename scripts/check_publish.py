"""Check the exact Git index for accidental data, credentials and local paths.

This is a conservative repository-specific guard, not a complete secret detector.
It inspects staged blobs, including during the first commit.
"""
import argparse
import json
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]
ROOT_FILES = {".gitignore", ".gitattributes", "README.md", "requirements.txt", "environment.yml"}
DIRS = {"scripts", "configs", "workflows", "docs", "env", "tests"}
SUFFIXES = {".py", ".json", ".toml", ".md", ".txt", ".yml", ".yaml"}
PATTERNS = {
    "GitHub credential": re.compile(r"(?:gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{30,})"),
    "Hugging Face credential": re.compile(r"hf_[A-Za-z0-9]{25,}"),
    "OpenAI-style credential": re.compile(r"sk-(?:proj-|svcacct-)?[A-Za-z0-9_-]{25,}"),
    "AWS access key": re.compile(r"(?:AKIA|ASIA)[0-9A-Z]{16}"),
    "private key": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    "Windows absolute path": re.compile(r"(?<![A-Za-z0-9_])[A-Za-z]:[\\/]"),
    "UNC path": re.compile(r"\\\\[A-Za-z0-9][A-Za-z0-9_.-]*\\"),
    "home or build path": re.compile(r"(?:file:///|/(?:home|Users|root)/)[A-Za-z0-9_.-]+"),
    "URL with credentials": re.compile(r"https?://[^\s/'\"]+:[^\s/'\"]+@"),
}
SECRET_KEYS = {"api_key", "apikey", "access_token", "refresh_token", "password", "secret", "client_secret", "huggingface_token"}


def secret_fields(value, prefix=""):
    found = []
    if isinstance(value, dict):
        for key, item in value.items():
            if key.lower() in SECRET_KEYS and item not in (None, ""):
                found.append(prefix + key)
            found.extend(secret_fields(item, prefix + key + "."))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            found.extend(secret_fields(item, prefix + str(index) + "."))
    return found


def inspect(name: str, data: bytes) -> list[str]:
    path = Path(name)
    reasons = []
    if name not in ROOT_FILES and (path.parts[0] not in DIRS or path.suffix.lower() not in SUFFIXES):
        reasons.append("outside publication allowlist")
    if name == "configs/local.toml" or any(p in {"__pycache__", "runs", "outputs", "cache", "images", "secrets"} for p in path.parts):
        reasons.append("private/runtime path")
    if len(data) > 500_000:
        reasons.append("over 500 KB text-file limit")
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        return reasons + ["not UTF-8 text"]
    if "\0" in text:
        reasons.append("binary data")
    for label, pattern in PATTERNS.items():
        for match in pattern.finditer(text):
            reasons.append(f"{label} at line {text.count(chr(10), 0, match.start()) + 1}")
    if path.suffix == ".json":
        try:
            value = json.loads(text)
            reasons.extend("populated secret field: " + p for p in secret_fields(value))
        except json.JSONDecodeError:
            reasons.append("invalid JSON")
    return reasons


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    tracked = subprocess.check_output(["git", "ls-files", "-z"], cwd=ROOT).decode("utf-8").split("\0")
    names = [n for n in tracked if n]
    if not names:
        raise SystemExit("Nothing staged/tracked; add the explicit publication directories first")
    issues, total = {}, 0
    for name in names:
        data = subprocess.check_output(["git", "show", ":" + name], cwd=ROOT)
        total += len(data)
        findings = inspect(name, data)
        if findings:
            issues[name] = findings
    result = {"files": len(names), "bytes": total, "issues": issues, "passed": not issues}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    raise SystemExit(1 if issues else 0)


if __name__ == "__main__":
    main()
