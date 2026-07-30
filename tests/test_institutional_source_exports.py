import json
import pathlib
import shutil
import subprocess
import sys

import pytest


ROOT = pathlib.Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures" / "institutional"


@pytest.mark.parametrize(("filename", "expected"), [
    ("ieee_xplore.ris", ("IEEE defect inspection with deep learning", "10.1109/TEST.2024.00001", 2024)),
    ("scopus.csv", ("Scopus manufacturing inspection", "10.1016/j.test.2023.01.001", 2023)),
    ("web_of_science.csv", ("Web of Science materials inspection", "10.1002/test.2022.001", 2022)),
    ("ei_compendex.csv", ("Compendex robotics inspection", "10.1016/j.comp.2021.001", 2021)),
    ("inspec.ris", ("Inspec control systems inspection", "10.1049/test.2020.001", 2020)),
])
def test_realistic_institutional_export_aliases_are_preserved(filename, expected):
    sys.path.insert(0, str(ROOT / "scripts"))
    from import_library import load
    item = load(FIXTURES / filename)[0]
    assert (item["title"], item["DOI"], item["year"]) == expected


def test_manifest_records_per_source_provenance_and_requires_completeness_evidence(tmp_path):
    ieee = tmp_path / "ieee_xplore.ris"
    scopus = tmp_path / "scopus.csv"
    shutil.copy(FIXTURES / "ieee_xplore.ris", ieee)
    shutil.copy(FIXTURES / "scopus.csv", scopus)
    manifest = {"sources": [
        {"source": "ieee_xplore", "input": ieee.name, "query": '"All Metadata": defect inspection',
         "scope_filters": {"years": "2020-2026", "languages": ["en"]}, "dedup_rule": "DOI",
         "exported_at": "2026-07-30T10:00:00Z", "reported_total": 1, "exported_count": 1,
         "export_limit": 2000, "completeness_basis": "reported_total_matches_export"},
        {"source": "scopus", "input": scopus.name, "query": "TITLE-ABS-KEY(defect inspection)",
         "scope_filters": {"years": "2020-2026", "languages": ["en"]}, "dedup_rule": "DOI",
         "exported_at": "2026-07-30T10:01:00Z"},
    ]}
    manifest_path = tmp_path / "institutional-exports.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    snapshot = tmp_path / "snapshot.json"
    subprocess.run([sys.executable, str(ROOT / "scripts" / "import_source_snapshots.py"),
                    "--manifest", str(manifest_path), "--out", str(snapshot)], check=True)
    sources = json.loads(snapshot.read_text(encoding="utf-8"))["queries"][0]["sources"]
    assert sources["ieee_xplore"]["complete"] is True
    assert sources["scopus"]["status"] == "partial"
    assert sources["ieee_xplore"]["provenance"]["sha256"]
    assert sources["ieee_xplore"]["provenance"]["query"] != sources["scopus"]["provenance"]["query"]


def test_missing_stable_ids_fail_before_a3(tmp_path):
    bad_export = tmp_path / "bad.csv"
    bad_export.write_text("Title,Publication Year\nNo identifier,2024\n", encoding="utf-8")
    manifest = {"sources": [{"source": "scopus", "input": bad_export.name, "query": "q",
                               "scope_filters": {"years": "2024"}, "dedup_rule": "DOI",
                               "exported_at": "2026-07-30T10:00:00Z"}]}
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    result = subprocess.run([sys.executable, str(ROOT / "scripts" / "import_source_snapshots.py"),
                             "--manifest", str(manifest_path), "--out", str(tmp_path / "snapshot.json")],
                            capture_output=True, text=True)
    assert result.returncode != 0
    assert "stable identifier" in result.stderr


def test_human_report_shows_threshold_calibration():
    sys.path.insert(0, str(ROOT / "scripts"))
    from run_audit import _english_report_markdown
    report = {"standards": {"calibration_basis": "domain_profile", "calibration_reference": "communications profile v1", "confirmed_by_user": True},
              "context": {"scope_application": {"in_scope_records": 1, "total_records": 1, "time_excluded_records": 0, "language_excluded_records": 0, "time_boundary": {}, "language_boundary": ["en"]}},
              "indicator_register": []}
    rendered = _english_report_markdown(report, [])
    assert "Threshold calibration" in rendered
    assert "communications profile v1" in rendered
    assert "confirmed by user" in rendered


def test_imported_snapshot_a3_is_only_estimated_when_every_source_is_complete(tmp_path):
    ieee = tmp_path / "ieee.ris"; scopus = tmp_path / "scopus.csv"
    shutil.copy(FIXTURES / "ieee_xplore.ris", ieee); shutil.copy(FIXTURES / "scopus.csv", scopus)
    common = {"scope_filters": {"years": "2020-2026"}, "dedup_rule": "DOI", "exported_at": "2026-07-30T10:00:00Z",
              "reported_total": 1, "exported_count": 1, "completeness_basis": "reported_total_matches_export"}
    entries = [{**common, "source": "ieee_xplore", "input": ieee.name, "query": "q1"},
               {**common, "source": "scopus", "input": scopus.name, "query": "q2"}]
    manifest_path = tmp_path / "exports.json"; manifest_path.write_text(json.dumps({"sources": entries}), encoding="utf-8")
    snapshot = tmp_path / "snapshot.json"
    subprocess.run([sys.executable, str(ROOT / "scripts" / "import_source_snapshots.py"), "--manifest", str(manifest_path), "--out", str(snapshot)], check=True)
    context = tmp_path / "context.json"; context.write_text(json.dumps({"review_type": "narrative"}), encoding="utf-8")
    library = tmp_path / "library.json"; library.write_text("[]", encoding="utf-8")
    out = tmp_path / "audit"
    command = [sys.executable, str(ROOT / "scripts" / "run_audit.py"), "--library", str(library), "--context", str(context), "--candidate-snapshots", str(snapshot), "--out", str(out)]
    subprocess.run(command, check=True)
    assert json.loads((out / "audit.json").read_text(encoding="utf-8"))["coverage"]["a3"]["status"] == "estimated_lower_bound"
    entries[1]["scope_filters"] = {"years": "2019-2026"}
    manifest_path.write_text(json.dumps({"sources": entries}), encoding="utf-8")
    subprocess.run([sys.executable, str(ROOT / "scripts" / "import_source_snapshots.py"), "--manifest", str(manifest_path), "--out", str(snapshot)], check=True)
    subprocess.run(command, check=True)
    assert json.loads((out / "audit.json").read_text(encoding="utf-8"))["coverage"]["a3"]["status"] == "partial_snapshot"
