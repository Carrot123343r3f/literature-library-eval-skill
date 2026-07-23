#!/usr/bin/env python3
"""Create a fully populated synthetic 3DGS audit example for documentation review."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "outputs" / "3DGS_narrative_eval_2026-07-22"
SEARCH = OUT / "search_r1"
OUT.mkdir(parents=True, exist_ok=True)
SEARCH.mkdir(parents=True, exist_ok=True)

topics = [
    {"name": "基础表示与渲染", "high_confidence_records": 3, "target_share": 0.25, "opposing_viewpoint": False},
    {"name": "压缩与加速", "high_confidence_records": 3, "target_share": 0.25, "opposing_viewpoint": True},
    {"name": "动态场景与4D", "high_confidence_records": 3, "target_share": 0.25, "opposing_viewpoint": True},
    {"name": "应用与系统", "high_confidence_records": 3, "target_share": 0.25, "opposing_viewpoint": False},
]

titles = [
    ("Gaussian Splatting for Real-Time Radiance Field Rendering", "ACM Digital Library", "基础表示与渲染", 2023, 12800),
    ("Mip-Splatting: Alias-free 3D Gaussian Splatting", "arXiv", "基础表示与渲染", 2023, 920),
    ("2D Gaussian Splatting for Geometrically Accurate Radiance Fields", "IEEE Xplore", "基础表示与渲染", 2024, 1450),
    ("Compact 3D Gaussian Splatting with Structured Pruning", "OpenAlex", "压缩与加速", 2024, 380),
    ("Scaffold-GS: Structured 3D Gaussians for View-Adaptive Rendering", "ACM Digital Library", "压缩与加速", 2024, 510),
    ("Efficient Gaussian Splatting under a Mobile Memory Budget", "arXiv", "压缩与加速", 2025, 96),
    ("4D Gaussian Splatting for Real-Time Dynamic Scene Rendering", "IEEE Xplore", "动态场景与4D", 2024, 760),
    ("Deformable 3D Gaussians for Monocular Dynamic Reconstruction", "OpenAlex", "动态场景与4D", 2024, 430),
    ("Gaussian Flow Fields for Long-Horizon Dynamic View Synthesis", "arXiv", "动态场景与4D", 2025, 88),
    ("StreetGaussian: Street-View Reconstruction with 3D Gaussians", "ACM Digital Library", "应用与系统", 2024, 610),
    ("Gaussian-SLAM: Photo-Realistic Dense Mapping with Gaussian Primitives", "IEEE Xplore", "应用与系统", 2024, 275),
    ("Gaussian Avatars for Real-Time Digital Human Rendering", "OpenAlex", "应用与系统", 2025, 132),
]

library = []
for i, (title, venue, topic, year, cited) in enumerate(titles, 1):
    library.append({
        "key": f"3DGS{i:02d}",
        "DOI": f"10.9999/3dgs.demo.{i:03d}",
        "title": title,
        "creators": [{"firstName": "Demo", "lastName": f"Author{i}"}],
        "date": f"{year}-06-15",
        "publicationTitle": venue,
        "abstractNote": f"This synthetic demonstration record studies {topic.lower()} in 3D Gaussian Splatting. It reports reconstruction quality, rendering speed, memory or temporal stability under a defined evaluation protocol.",
        "url": f"https://example.org/3dgs-demo-{i:02d}",
        "open_access_url": f"https://example.org/3dgs-demo-{i:02d}/pdf" if i != 5 else "",
        "attachments": [{"path": f"attachments/3dgs-demo-{i:02d}.pdf"}] if i <= 9 else [],
        "source": venue,
        "collection": "3DGS研究/示例库",
        "topic": topic,
        "cited_by_count": cited,
        "screening_status": "included" if i <= 10 else "included_with_caveat",
    })

gold = [{"title": library[i]["title"], "DOI": library[i]["DOI"]} for i in range(8)]
benchmark = [{"title": library[i]["title"], "DOI": library[i]["DOI"]} for i in range(6)] + [{"title": "Known missing 3DGS benchmark item", "DOI": "10.9999/3dgs.demo.missing"}]
query_hits = [{"title": library[i]["title"], "DOI": library[i]["DOI"], "openalex_id": f"W_DEMO_{i:02d}", "source": "OpenAlex"} for i in range(7)]
query_hits += [{"title": "Gaussian Rendering for Robotics", "DOI": "10.9999/3dgs.demo.new.01", "openalex_id": "W_DEMO_NEW_01", "source": "OpenAlex"}]

context = {
    "research_question": "3D Gaussian Splatting 在表示、效率、动态场景和工程应用中的进展是什么？",
    "review_type": "叙事综述",
    "profile": "计算机与AI",
    "library_name": "3DGS synthetic demonstration library",
    "year_start": 2023,
    "year_end": 2026,
    "languages": ["en"],
    "initial_query": "(3D Gaussian Splatting OR 3DGS) AND (rendering OR reconstruction)",
    "keywords": ["3D Gaussian Splatting", "3DGS", "dynamic scenes", "real-time rendering"],
    "taxonomy": topics,
    "topic_source_counts": {
        "基础表示与渲染": {"ACM Digital Library": 1, "arXiv": 1, "IEEE Xplore": 1},
        "压缩与加速": {"OpenAlex": 1, "ACM Digital Library": 1, "arXiv": 1},
        "动态场景与4D": {"IEEE Xplore": 1, "OpenAlex": 1, "arXiv": 1},
        "应用与系统": {"ACM Digital Library": 1, "IEEE Xplore": 1, "OpenAlex": 1},
    },
    "viewpoint_framework": {
        "claim": "结构化压缩是否在保持视图质量的同时显著降低 3DGS 的资源开销？",
        "contested": True,
        "records_assessed": 12,
        "counts": {"supports_claim": 5, "challenges_claim": 3, "mixed_or_conditional": 2, "unclassified": 2},
        "classification_method": "题名+摘要双人规则初筛，抽样 4/12 条人工核验",
        "sample_verified": 4,
    },
    "frontier_coverage_verdict": "pass",
    "version_currency_verdict": "pass",
    "independent_validation_passed": True,
    "last_successful_search": {"OpenAlex": "2026-07-22", "Crossref": "2026-07-22", "arXiv": "2026-07-21"},
    "planned_sources": ["OpenAlex", "Crossref", "arXiv"],
    "dev_set": [{"doi": f"10.9999/3dgs.demo.dev{i}"} for i in range(1, 5)],
    "validation_set": [{"doi": "10.9999/3dgs.demo.validation1"}],
    "dev_validation_overlap_check": True,
    "search_iterations": [
        {"iteration_id": "q0", "change_type": "initial", "change_description": "执行用户提供的初始检索式", "change_source": "user_provided", "execution_date": "2026-07-20", "queries": {"db_OpenAlex": "(3D Gaussian Splatting OR 3DGS) AND (rendering OR reconstruction)"}, "results": {"dev_recall": 0.625, "validation_recall": 0.50}, "decision": "continue"},
        {"iteration_id": "q1", "parent_iteration": "q0", "change_type": "add_synonym", "change_description": "加入 dynamic 术语", "change_source": "agent_refined", "execution_date": "2026-07-21", "queries": {"db_OpenAlex": "(3D Gaussian Splatting OR 3DGS) AND dynamic"}, "results": {"dev_recall": 0.75, "validation_recall": 0.625}, "decision": "continue"},
        {"iteration_id": "q2", "parent_iteration": "q1", "change_type": "modify_field", "change_description": "增加标题字段诊断", "change_source": "agent_refined", "execution_date": "2026-07-22", "queries": {"db_OpenAlex": "title:(3D Gaussian Splatting OR 3DGS)"}, "results": {"dev_recall": 0.875, "validation_recall": 0.75}, "decision": "a2_stop"},
    ],
    "saturation_rounds": [
        {"round_id": "sat-r1", "query_id": "q2", "query_status": "frozen_robust", "completed": True, "core_before": 12, "included_high": 1, "screening_status": "screened", "pathway_yields": [{"pathway": "db_boolean", "completed": True, "yield": 0.04}, {"pathway": "backward_citation", "completed": True, "yield": 0.03}, {"pathway": "forward_citation", "completed": True, "yield": 0.01}, {"pathway": "related_articles", "completed": True, "yield": 0.02}, {"pathway": "standards_guidelines", "completed": True, "yield": 0.00}]},
        {"round_id": "sat-r2", "query_id": "q2", "query_status": "frozen_robust", "completed": True, "core_before": 13, "included_high": 0, "screening_status": "screened", "pathway_yields": [{"pathway": "db_boolean", "completed": True, "yield": 0.01}, {"pathway": "backward_citation", "completed": True, "yield": 0.00}, {"pathway": "forward_citation", "completed": True, "yield": 0.01}, {"pathway": "related_articles", "completed": True, "yield": 0.00}, {"pathway": "standards_guidelines", "completed": True, "yield": 0.00}]},
        {"round_id": "sat-r3", "query_id": "q2", "query_status": "frozen_robust", "completed": True, "core_before": 13, "included_high": 0, "screening_status": "screened", "pathway_yields": [{"pathway": "db_boolean", "completed": True, "yield": 0.00}, {"pathway": "backward_citation", "completed": True, "yield": 0.00}, {"pathway": "forward_citation", "completed": True, "yield": 0.00}, {"pathway": "related_articles", "completed": True, "yield": 0.00}, {"pathway": "standards_guidelines", "completed": True, "yield": 0.00}]},
    ],
    "planned_pathways": ["db_boolean", "backward_citation", "forward_citation", "related_articles", "standards_guidelines"],
    "independent_pathways": [
        {"pathway": "db_boolean", "completed": True, "yield": 0.04},
        {"pathway": "backward_citation", "completed": True, "yield": 0.03},
        {"pathway": "forward_citation", "completed": True, "yield": 0.01},
        {"pathway": "related_articles", "completed": True, "yield": 0.02},
        {"pathway": "standards_guidelines", "completed": True, "yield": 0.00},
    ],
    "search_query_versions": [
        {"query_id": "q0", "origin": "user_provided", "query": "(3D Gaussian Splatting OR 3DGS) AND (rendering OR reconstruction)", "source": "OpenAlex", "date": "2026-07-20", "hits": 86, "status": "complete"},
        {"query_id": "q1", "origin": "agent_refined", "query": "(3D Gaussian Splatting OR 3DGS) AND dynamic", "source": "OpenAlex", "date": "2026-07-21", "hits": 54, "status": "complete"},
        {"query_id": "q2", "origin": "agent_refined", "query": "title:(3D Gaussian Splatting OR 3DGS)", "source": "OpenAlex", "date": "2026-07-22", "hits": 31, "status": "complete"},
    ],
    "search_initial_query_origin": "user_provided",
    "standards": {"a1_min_recall": 0.75, "a2_min_recall": 0.70, "f_abstract_rate": 0.80, "f_access_rate": 0.60, "f_provenance_rate": 0.85, "b_ggr_threshold": 0.02, "b_drr_threshold": 0.05, "recency_years": 3, "recency_min_share": 0.40, "d_freshness_days": 30, "confirmed_by_user": True},
}

search_meta = {
    "queries": context["search_query_versions"],
    "search_rounds": [],
    "saturation_rounds": context["saturation_rounds"],
    "search_iterations": context["search_iterations"],
    "dev_set": context["dev_set"],
    "validation_set": context["validation_set"],
    "dev_validation_overlap_check": True,
    "planned_pathways": context["planned_pathways"],
    "independent_pathways": context["independent_pathways"],
    "dev_recall": 0.875, "dev_recall_total": 8,
    "validation_recall": 0.75, "validation_recall_total": 8,
    "validation_source": "冻结的外部时间留出集",
    "a2_evidence_status": "measured",
    "initial_query_origin": "user_provided",
    "first_round_discovery_ggr": 0.25,
    "potential_additions_count": 8,
}

run_log = {"queries": [
    {"source": "OpenAlex", "query": q["query"], "fields": "title,abstract,doi,publication_year", "date": q["date"], "filters": "language:en;year:2023-2026", "result_count": q["hits"], "completion_status": "complete"}
    for q in context["search_query_versions"]
]}
decisions = [{"item_id": x["key"], "decision": "include", "reason": f"与主题{x['topic']}直接相关，摘要提供可比较的实验或系统信息。", "reviewer": "demo-reviewer"} for x in library]
dedup = {"exact_identifier_groups": [], "uncertain_title_year_candidates": [], "possible_version_families": [{"items": ["3DGS01", "3DGS01-preprint"], "decision": "retain_both", "reason": "预印本与会议正式版本保留版本关系但只计一项"}]}
snapshot = {"sources": {
    "OpenAlex": {"status": "complete", "items": [{"DOI": x["DOI"], "title": x["title"]} for x in library[:8]]},
    "Crossref": {"status": "complete", "items": [{"DOI": x["DOI"], "title": x["title"]} for x in library[4:]]},
    "arXiv": {"status": "complete", "items": [{"DOI": x["DOI"], "title": x["title"]} for x in library[1:6]]},
}}
evidence_manifest = {"schema_version": "1.0", "datasets": {
    "dev": {"role": "dev", "path": "dev_set.json", "source_routes": ["OpenAlex"], "used_tested_query": True, "used_for_query_optimization": True, "frozen_at": "2026-07-20T10:00:00+08:00"},
    "validation": {"role": "validation", "path": "validation_set.json", "source_routes": ["backward_citation", "time_holdout"], "used_tested_query": False, "used_for_query_optimization": False, "frozen_at": "2026-07-20T10:05:00+08:00"},
    "b3_validation": {"role": "b3_validation", "path": "b3_validation.json", "source_routes": ["expert_route"], "used_tested_query": False, "used_for_query_optimization": False, "frozen_at": "2026-07-20T10:10:00+08:00"},
}, "relationships": {"a2_validation_dataset": "validation", "b3_validation_dataset": "b3_validation", "a3_source_ids": ["OpenAlex", "Crossref", "arXiv"], "b2_pathway_source_ids": ["backward_citation", "forward_citation", "related_articles"]}}

files = {
    OUT / "library.json": library, OUT / "gold_set.json": gold, OUT / "benchmark.json": benchmark,
    OUT / "context.json": context, OUT / "run_log.json": run_log, OUT / "decision_log.json": {"decisions": decisions},
    OUT / "deduplication_log.json": dedup, OUT / "source_snapshot.json": snapshot,
    OUT / "evidence-manifest.json": evidence_manifest, SEARCH / "query-hits.json": query_hits,
    SEARCH / "search_meta.json": search_meta,
}
for path, data in files.items():
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"Wrote {len(files)} demo inputs to {OUT}")
