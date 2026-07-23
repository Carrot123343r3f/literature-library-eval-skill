import unittest

from scripts.evidence_isolation import inspect_manifest
from scripts.run_audit import _validate_run_config
from scripts.search_for_eval import resolve_query_inputs
from scripts.search_iterator import validate


class RegressionTests(unittest.TestCase):
    def test_run_config_accepts_evidence_manifest_contract(self):
        config = {
            "schema_version": "1.0",
            "project": {
                "research_question": "industrial defect detection",
                "review_type": "narrative",
                "scope_status": "in_scope",
            },
            "library": {"provided": True, "path": "library.json", "format": "json"},
            "automation": {"allow_search": True},
            "evidence_inputs": {"evidence_manifest": "evidence-manifest.json"},
            "output": {"out_dir": "out"},
        }
        self.assertEqual(_validate_run_config(config), [])

    def test_manifest_detects_shared_stable_ids_without_doi(self):
        manifest = {
            "datasets": {
                "dev": {"item_ids": ["openalex:W1"]},
                "validation": {
                    "item_ids": ["openalex:W1"],
                    "used_tested_query": False,
                    "used_for_query_optimization": False,
                    "source_routes": ["holdout"],
                    "frozen_at": "2026-07-23T00:00:00Z",
                },
            },
            "relationships": {},
        }
        result = inspect_manifest(manifest)
        self.assertEqual(result["status"], "invalid")
        self.assertEqual(result["dev_validation_overlap_count"], 1)

    def test_manifest_rejects_metadata_only_validation_dataset(self):
        result = inspect_manifest({
            "datasets": {"validation": {
                "used_tested_query": False,
                "used_for_query_optimization": False,
                "source_routes": ["holdout"],
                "frozen_at": "2026-07-23T00:00:00Z",
            }},
            "relationships": {},
        })
        self.assertEqual(result["status"], "invalid")

    def test_run_config_research_question_fills_missing_search_keywords(self):
        keywords, pico = resolve_query_inputs(
            {"search_decomposition": {"pico": {
                "object": {"value": "industrial defects", "source": "user_provided"},
                "technology": {"value": "vision inspection", "source": "user_provided"},
            }}},
            {"project": {"research_question": "industrial defect detection"}},
        )
        self.assertEqual(keywords, ["industrial defect detection"])
        self.assertEqual(pico["object"]["term"], "industrial defects")

    def test_iterator_rejects_multi_unit_change(self):
        data = {
            "dev_set": [{"doi": f"10.1/{i}"} for i in range(3)],
            "validation_set": [{"openalex_id": "W4"}],
            "dev_validation_overlap_check": True,
            "iterations": [
                {
                    "iteration_id": "v1",
                    "change_type": "initial",
                    "changed_units": [],
                    "change_description": "initial",
                    "change_source": "user",
                    "queries": {"db_openalex": "q"},
                    "execution_date": "2026-07-23",
                    "results": {"dev_recall": 0.1},
                },
                {
                    "iteration_id": "v2",
                    "parent_iteration": "v1",
                    "change_type": "add_synonym",
                    "changed_units": ["synonym:a", "synonym:b"],
                    "change_description": "two changes",
                    "change_source": "test",
                    "queries": {"db_openalex": "q2"},
                    "execution_date": "2026-07-23",
                    "results": {"dev_recall": 0.2},
                },
            ],
        }
        errors, _ = validate(data)
        self.assertTrue(any("exactly one changed_units" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
