"""Create privacy-preserving manifests for standalone workflow modules."""
import datetime as dt
import hashlib
import json
import pathlib
import platform
import sys
from audit_core.contracts import public_value


def _public(value):
    """Compatibility alias for the shared public-artifact redactor."""
    return public_value(value)


def _sha256(payload):
    return hashlib.sha256(payload).hexdigest()


def write_manifest(out, module, schema_version, artifacts, step_status):
    out = pathlib.Path(out); inputs = out / "inputs"; inputs.mkdir(parents=True, exist_ok=True)
    manifest = {"schema_version": schema_version, "module": module, "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
                "python_version": sys.version.split()[0], "platform": platform.platform(), "record_source_paths": False,
                "step_status": step_status, "input_files": {}}
    for label, path in sorted(artifacts.items()):
        entry = {"provided": bool(path)}
        source = pathlib.Path(path) if path else None
        if source and source.is_file():
            payload = source.read_bytes()
            archive_status = "hash_only_non_json"
            if source.suffix.lower() == ".json":
                try: payload = json.dumps(_public(json.loads(payload)), ensure_ascii=False, indent=2).encode("utf-8")
                except (UnicodeDecodeError, json.JSONDecodeError):
                    archive_status = "hash_only_unparseable_json"
                else:
                    archive_status = "redacted_json_copy"
            digest = _sha256(payload)
            entry.update({"sha256": digest, "source_filename": source.name, "archive_status": archive_status})
            if archive_status == "redacted_json_copy":
                destination = inputs / f"{label}__{digest[:12]}.json"
                if not destination.exists(): destination.write_bytes(payload)
                entry["copied_to"] = str(destination.relative_to(out))
        manifest["input_files"][label] = entry
    (out / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest
