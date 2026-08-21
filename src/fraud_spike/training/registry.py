import json, subprocess, hashlib, datetime
from pathlib import Path

def _git_commit() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"]).decode().strip()
    except Exception:
        return "unknown"

def _file_hash(path: str) -> str:
    h = hashlib.sha256()
    try:
        h.update(Path(path).read_bytes())
    except FileNotFoundError:
        return "no_file"
    return h.hexdigest()[:12]

def write_manifest(model_path: str, metrics: dict, manifest_path: str = "models/manifest.json") -> dict:
    manifest = {
        "model_version": _file_hash(model_path),
        "trained_at": datetime.datetime.utcnow().isoformat() + "Z",
        "git_commit": _git_commit(),
        "metrics": metrics,
    }
    Path(manifest_path).parent.mkdir(parents=True, exist_ok=True)
    Path(manifest_path).write_text(json.dumps(manifest, indent=2))
    return manifest
