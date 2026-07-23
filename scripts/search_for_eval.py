#!/usr/bin/env python3
"""多源候选发现/诊断性检索器：构造代表性检索式 → 在线执行 → 产出 A2 的诊断命中、B 的 discovery candidates、潜在新增清单。

闭环：本脚本产出 → agent 把 query versions/iterations 合并进 context.json 计算 A2；固定稳健检索式的实际饱和度另行写入 saturation_rounds，供 B1/B2 计算。
定位：减少 A2/B 的 missing-input 比例，而非自动得出 A2 结论或 B 饱和证据。
A2 只做稳定 ID 匹配（DOI/arXiv/OpenAlex ID），标题候选另存为人工核验参考。
B 的 included_high=0 直至人工筛选确认——discovery candidates ≠ 纳入项。

Dev/validation set separation（v2）：
  --dev-set 指定开发集（用于迭代反馈），--validation-set 指定独立验证集（用于最终 A2 判定）。
  两个集合不应有重叠。若只提供 --benchmark，整套作为 dev_set 使用，validation_set 为空，
  A2 将标注为 estimated 证据状态。
  独立验证集不参与检索式迭代——一旦用于调整检索式，就"烧掉"了独立性。
  --initial-query 保存用户提供的 q0，并以 q0-user 原样执行；未提供时才由 PICO/keywords 生成 ai_generated q0。

诊断路径可复算性：diagnostic_pathway_yields 中每条路径附带 candidates（候选数）、
screened_high_confidence（高置信筛选数）、new_high_confidence（此前未发现的）和
dedup_rule（去重规则），供第三方从 query-hits.json 独立复算 yield。

工程 PICO 分解（v2）：
  接受 --pico 参数（JSON 文件），内含 object/technology/performance/context 四要素分解。
  用于指导多源异构语法映射——每个来源选择其支持的字段语法，不把同一字符串原样投到不同数据库。
"""
import argparse, json, re, time, sys, pathlib
sys.stdout.reconfigure(encoding='utf-8')
try:
    from stable_ids import stable_ids
    from collect_open_sources import COLLECTORS
except ImportError:  # pragma: no cover - package-style fallback
    from scripts.stable_ids import stable_ids
    from scripts.collect_open_sources import COLLECTORS

def norm(t):
    """Normalize title for comparison — consistent with run_audit.title()."""
    return re.sub(r'[^\w]', '', str(t or '').casefold())

def ids_for_gold(g):
    """Extract canonical stable IDs from a benchmark/dev/validation record."""
    return stable_ids(g)

def entry_ids(entry):
    """Extract canonical stable IDs from a multi-source query hit."""
    return stable_ids(entry)

def compute_recall(gold_set, hit_ids_set):
    """Compute recall at item level. Each gold item matched if any stable ID overlaps."""
    gold_with_ids = [g for g in gold_set if isinstance(g, dict) and ids_for_gold(g)]
    if not gold_with_ids:
        return None, 0
    matched = sum(1 for g in gold_with_ids if ids_for_gold(g) & hit_ids_set)
    return round(matched / len(gold_with_ids), 3), len(gold_with_ids)


def recall_diagnostics(records, hit_ids_set):
    """Expose why a recall denominator or match is incomplete without title matching."""
    records = [r for r in (records or []) if isinstance(r, dict)]
    with_ids = [r for r in records if ids_for_gold(r)]
    missing_id_titles = [str(r.get("title") or "(untitled)") for r in records if not ids_for_gold(r)]
    matched = sum(1 for r in with_ids if ids_for_gold(r) & hit_ids_set)
    return {
        "records_total": len(records), "records_with_stable_id": len(with_ids),
        "records_without_stable_id": len(records) - len(with_ids), "matched_records": matched,
        "unmatched_records": len(with_ids) - matched,
        "missing_id_titles": missing_id_titles[:15],
        "accepted_identifier_types": ["DOI", "OpenAlex", "arXiv", "PMID", "PMCID"],
    }

def build_queries(keywords, pico=None):
    """从关键词构造宽/中/窄梯度检索式。若提供 PICO 分解，多源异构语法映射。

    PICO 格式：{"object": {...}, "technology": {...},
                "performance": {...}, "context": {...},
                "supplements": [...]}
    若 pico 不为空：使用 PICO 要素构建检索式而非原始 keywords。
    """
    if pico and isinstance(pico, dict):
        # Build progressively from all four engineering search units.  The
        # first unit anchors the topic; each later unit adds one controlled
        # constraint so every query remains an atomic refinement.
        def unit_text(name):
            value = pico.get(name, {})
            if isinstance(value, dict):
                value = value.get("term") or value.get("value") or ""
            return str(value or "").strip()

        units = [(name, unit_text(name)) for name in ("object", "technology", "performance", "context")]
        units = [(name, value) for name, value in units if value]
        if not units:
            return build_queries(keywords)  # fallback to keywords
        primary = units[0][1].split(";")[0].strip()
        queries = [('q0-ai', f'"{primary}"')]
        accumulated = [primary]
        for name, value in units[1:]:
            term = value.split(";")[0].strip()
            if term and norm(term) not in {norm(x) for x in accumulated}:
                accumulated.append(term)
                queries.append((f'q{len(queries)}-add-{name}', ' '.join(f'"{x}"' for x in accumulated)))
            if len(queries) >= 4:
                break
        queries.append((f'q{len(queries)}-title-field', f'title:"{primary}"'))
        return queries[:5]

    # Original keyword-based building
    if not keywords:
        return []
    core = keywords[0]
    queries = [('q0-ai', f'"{core}"')]
    seen_sub = {norm(core)}
    for sub in keywords[1:5]:
        if norm(sub) not in seen_sub:
            queries.append((f'q{len(queries)}-add-term', f'"{core}" {sub}'))
            seen_sub.add(norm(sub))
        if len(queries) >= 4: break
    queries.append((f'q{len(queries)}-title-field', f'title:"{core}"'))
    return queries[:5]


def refine_user_q0(initial_query, keywords):
    """Create one transparent, atomic OpenAlex diagnostic refinement of user q0."""
    for term in keywords[1:6]:
        if term and norm(term) not in norm(initial_query):
            return [('q0-user', initial_query), ('q1-add-term', f'{initial_query} "{term}"')]
    return [('q0-user', initial_query)]


def default_sources(context):
    """Choose repeatable open-source coverage without pretending it is exhaustive."""
    profile = str(context.get("profile") or " ".join(context.get("engineering_profile", []))).casefold()
    sources = ["openalex", "crossref"]
    if any(token in profile for token in ("computer", "ai", "software", "electronic", "communication")):
        sources.append("arxiv")
    if any(token in profile for token in ("biomedical", "bio", "medical")):
        sources.append("europepmc")
    return sources


SOURCE_SYNTAX = {
    "openalex": "OpenAlex works search parameter (broad concept search)",
    "crossref": "Crossref bibliographic query parameter (metadata concept search)",
    "arxiv": "arXiv all-field query parameter (preprint concept search)",
    "europepmc": "Europe PMC query parameter (biomedical metadata search)",
}


def query_text_for_source(query):
    """Remove diagnostic field notation before passing a concept to open APIs.

    Each collector owns the final source-specific URL syntax.  The normalised
    concept string is retained in the log so this translation remains visible.
    """
    return re.sub(r"\btitle:\s*", "", str(query or "")).replace('"', " ").strip()


def hit_key(item):
    identifiers = sorted(entry_ids(item))
    return identifiers[0] if identifiers else "title:" + norm(item.get("title"))


def main():
    p = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    p.add_argument('--library', required=True, help='题录 JSON（判断在库内）')
    p.add_argument('--context', required=True, help='context.json（读 keywords/profile）')
    p.add_argument('--benchmark', help='A1 基准集 JSON；当 --dev-set 和 --gold 均未提供时复用为 dev_set')
    p.add_argument('--gold', help='A2 gold set JSON（若需要独立于 benchmark；v2 建议使用 --dev-set + --validation-set）')
    p.add_argument('--dev-set', help='[v2] 开发集 JSON — 用于迭代检索式（多次使用）')
    p.add_argument('--validation-set', help='[v2] 独立验证集 JSON — 仅用于最终 A2 判定（看过即"烧掉"，不用于调检索式）')
    p.add_argument('--pico', help='[v2] 工程 PICO 分解 JSON — object/technology/performance/context')
    p.add_argument('--initial-query', help='用户提供的原始检索式 q0；首轮优先执行并原样记录，不被 AI 静默替换')
    p.add_argument('--ai-provisional', action='store_true',
                   help='首轮 AI 主导模式：开发/验证集和自动筛选结果均标 automated-screening，而非 measured')
    p.add_argument('--sources', default='auto',
                   help='首轮开放来源：auto（按 profile 选 OpenAlex+Crossref，并按需加 arXiv/Europe PMC），或逗号列表')
    p.add_argument('--out', required=True)
    p.add_argument('--max-per-query', type=int, default=50,
                   help='每来源/检索式最大记录数；达到上限时标记为 partial snapshot')
    a = p.parse_args()

    library = json.load(open(a.library, encoding='utf-8-sig'))
    ctx = json.load(open(a.context, encoding='utf-8-sig'))

    # ── Dev/validation set resolution (v2) ──
    dev_set = validation_set = None
    dev_source = val_source = ""

    if a.dev_set:
        dev_set = json.load(open(a.dev_set, encoding='utf-8-sig'))
        dev_set = dev_set if isinstance(dev_set, list) else dev_set.get("items", [])
        dev_source = "独立 dev-set 文件"
    elif a.gold:
        dev_set = json.load(open(a.gold, encoding='utf-8-sig'))
        dev_set = dev_set if isinstance(dev_set, list) else dev_set.get("items", [])
        dev_source = "gold set (无独立验证集)"
    elif a.benchmark:
        dev_set = json.load(open(a.benchmark, encoding='utf-8-sig'))
        dev_set = dev_set if isinstance(dev_set, list) else dev_set.get("items", [])
        dev_source = "benchmark (无独立验证集)"

    if a.validation_set:
        validation_set = json.load(open(a.validation_set, encoding='utf-8-sig'))
        validation_set = validation_set if isinstance(validation_set, list) else validation_set.get("items", [])
        val_source = "AI 机械留出集（自动初筛，非最终独立验证）" if a.ai_provisional else "独立验证集"
        if not dev_set:
            dev_set = validation_set
            dev_source = "validation_set 复用（不推荐——将被 A2 标记为 estimated）"

    # Check dev/val overlap
    if dev_set and validation_set:
        dev_dois = set()
        for e in dev_set:
            for did in ids_for_gold(e):
                dev_dois.add(did)
        val_dois = set()
        for e in validation_set:
            for did in ids_for_gold(e):
                val_dois.add(did)
        overlap = dev_dois & val_dois
        if overlap:
            print(f"WARNING: Dev/validation sets overlap on {len(overlap)} identifier(s). A2 independence is compromised.")

    # ── PICO decomposition ──
    pico = None
    if a.pico:
        pico = json.load(open(a.pico, encoding='utf-8-sig'))

    lib_stable_ids = set().union(*(ids_for_gold(row) for row in library if isinstance(row, dict))) if library else set()

    keywords = ctx.get('keywords', []) or ([ctx.get('research_question')] if ctx.get('research_question') else [])
    core_terms = [k.lower() for k in keywords[:3]]
    initial_query = a.initial_query or ctx.get('initial_query') or ctx.get('user_query')
    queries = refine_user_q0(initial_query, keywords) if initial_query else build_queries(keywords, pico)
    if pico:
        # Use PICO terms for core terms when available
        pico_core = []
        for key in ("object", "technology"):
            t = pico.get(key, {}).get("term", "")
            if t:
                pico_core.extend(t.split(";"))
        if pico_core:
            core_terms = [t.strip().lower() for t in pico_core[:3]]
    print(f'构造 {len(queries)} 条检索式，核心词: {core_terms[:3]}')
    sources = default_sources(ctx) if a.sources == 'auto' else [x.strip() for x in a.sources.split(',') if x.strip()]
    sources = [x for x in sources if x in COLLECTORS]
    if len(sources) < 2:
        p.error('首轮检索至少需要两个受支持的开放来源，以形成多源诊断；支持 openalex,crossref,arxiv,europepmc')
    print(f'首轮来源: {", ".join(sources)}')

    all_hits, seen, queries_record, potential_add, search_iterations = [], set(), [], [], []
    source_hits = {source: [] for source in sources}
    for label, q in queries:
        per_source_queries, q_failures, q_count = {}, [], 0
        for source in sources:
            collector = COLLECTORS[source]
            translated_query = query_text_for_source(q)
            try:
                result = collector(translated_query, a.max_per_query)
                status = "complete" if result.get("complete") else "partial"
                raw_hits = result.get("items", [])
            except Exception as exc:
                status, raw_hits = "failed", []
                q_failures.append(f"{source}: {str(exc)[:160]}")
            per_source_queries[source] = q
            source_count = 0
            for raw in raw_hits:
                item = dict(raw, query_label=label, source=source)
                key = hit_key(item)
                if key == "title:":
                    continue
                source_hits[source].append(item)
                if key not in seen:
                    seen.add(key)
                    all_hits.append(item)
                    q_count += 1
                source_count += 1
                item["source_query_count"] = source_count
                in_lib = bool(entry_ids(item) & lib_stable_ids)
                if not in_lib and item.get("title"):
                    title_text = item["title"].casefold()
                    primary_ok = bool(core_terms) and core_terms[0] in title_text
                    secondary_ok = len(core_terms) < 2 or any(term in title_text for term in core_terms[1:])
                    if primary_ok and secondary_ok:
                        potential_add.append(dict(item, automated_screen_rule="title contains primary concept plus a supplemental concept"))
            record = {'source': source, 'query': q, 'translated_query': translated_query, 'label': label,
                      'query_id': 'q0' if label in ('q0-user', 'q0-ai') else label.split('-', 1)[0],
                      'date': time.strftime('%Y-%m-%d'), 'hits': source_count, 'status': status,
                      'note': 'complete snapshot' if status == 'complete' else ('limit reached; partial snapshot' if status == 'partial' else 'failed')}
            queries_record.append(record)
            if status == "failed":
                q_failures.append(f"{source} request failed")
        query_id = 'q0' if label in ('q0-user', 'q0-ai') else label.split('-', 1)[0]
        if label == 'q0-user':
            origin, change_type, change_description = 'user_provided', 'initial', 'Preserve and execute the user-provided q0.'
        elif label == 'q0-ai':
            origin, change_type, change_description = 'ai_generated', 'initial', 'AI-generated initial diagnostic query from the supplied keywords/PICO.'
        elif label.endswith('title-field'):
            origin, change_type, change_description = 'agent_refined', 'modify_field', 'Restrict the same concept to the title field for a narrow diagnostic comparison.'
        else:
            origin, change_type, change_description = 'agent_refined', 'add_synonym', 'Add one supplemental term to q0 for an atomic diagnostic comparison.'
        for record in queries_record[-len(sources):]:
            record['origin'] = origin
        search_iterations.append({
            'iteration_id': query_id,
            'parent_iteration': None if query_id == 'q0' else 'q0',
            'change_type': change_type,
            'change_description': change_description,
            'change_source': 'multi-source diagnostic search',
            'queries': per_source_queries,
            'execution_date': time.strftime('%Y-%m-%d'),
            'results': {'total_hits': q_count, 'deduplicated_hits': q_count,
                        'dev_recall': None, 'validation_recall': None,
                        'discovery_candidates': 0},
            'failures': q_failures,
            'decision': 'continue',
            'evidence_status': 'diagnostic_only',
        })
        print(f'  [{label}] {q[:45]:45s} -> {q_count} 去重命中（{", ".join(sources)}）')
        time.sleep(0.3)

    # ── Build hit ID set for recall computation ──
    hit_ids_set = set()
    for h in all_hits:
        hit_ids_set |= entry_ids(h)

    # ── Compute dev_recall + validation_recall ──
    dev_recall, dev_total = compute_recall(dev_set, hit_ids_set) if dev_set else (None, 0)
    val_recall, val_total = compute_recall(validation_set, hit_ids_set) if validation_set else (None, 0)
    dev_diagnostics = recall_diagnostics(dev_set, hit_ids_set)
    validation_diagnostics = recall_diagnostics(validation_set, hit_ids_set)

    # ── A2: evaluate against gold/dev_set for backward compat ──
    gold = dev_set or []  # default gold = dev_set
    gold_ids = set()
    for g in gold:
        gold_ids |= ids_for_gold(g)
    id_matched = gold_ids & hit_ids_set
    gold_with_ids = [g for g in gold if isinstance(g, dict) and ids_for_gold(g)]
    a2_total_with_id = len(gold_with_ids)
    a2_matched_id = sum(1 for g in gold_with_ids if ids_for_gold(g) & hit_ids_set)
    a2_total_all = len(gold)
    a2_recall_id = round(a2_matched_id / a2_total_with_id, 3) if a2_total_with_id else None

    # Title candidate matching for cross-system manual verification
    gold_titles = {norm(g.get('title')) for g in gold if g.get('title')}
    hit_titles = {norm(h.get('title')) for h in all_hits if h.get('title')}
    title_candidate_matches = gold_titles & hit_titles
    a2_title_candidates = len(title_candidate_matches)
    a2_missing_titles = [g.get('title', '') for g in gold
                         if norm(g.get('title')) and norm(g.get('title')) not in hit_titles]

    # ── B first-run growth evidence ──
    lib_size = len(library)
    discovery_candidate_count = len(potential_add)
    first_run_status = 'automated-screening' if a.ai_provisional else 'discovery_only'
    search_rounds, cumulative_screened = [], 0
    for label, _query in queries:
        screened = [item for item in potential_add if item.get('query_label') == label]
        screened_keys = {hit_key(item) for item in screened}
        auto_count = len(screened_keys) if a.ai_provisional else 0
        search_rounds.append({'pathway': label, 'completed': True,
                              'core_before': lib_size + cumulative_screened, 'included_high': 0,
                              'screened_inclusions': auto_count, 'discovery_candidates': len(screened_keys),
                              'screening_status': first_run_status,
                              'note': ('AI 初筛：标题同时命中核心概念与补充概念；仅用于首轮候选诊断，不能作为 B1/B2 饱和结论，需摘要/全文与人工抽查升级。'
                                       if a.ai_provisional else '自动检索器产出的是发现候选，未经筛选不能计入 GGR 分子。')})
        cumulative_screened += auto_count
    discovery_ggr = round(discovery_candidate_count / lib_size, 4) if lib_size else None
    for iteration in search_iterations:
        label = iteration['iteration_id']
        iteration['results']['discovery_candidates'] = sum(
            1 for item in potential_add if item.get('query_label') == label or item.get('query_label', '').startswith(label)
        )
        if label == search_iterations[-1]['iteration_id']:
            iteration['results']['dev_recall'] = dev_recall
            iteration['results']['validation_recall'] = val_recall
            iteration['decision'] = 'continue' if len(search_iterations) < 2 else 'diagnostic_bundle_complete'

    # Source-level candidate yields.  Different database indexes are useful
    # triangulation, but are only *partially* independent: their first-run DRR
    # is diagnostic evidence, never proof of saturation.
    covered, marginal = set(), []
    for source in sources:
        source_unique = {}
        for item in source_hits[source]:
            source_unique.setdefault(hit_key(item), item)
        candidates = list(source_unique.values())
        screened = [item for item in potential_add if item.get('source') == source]
        screened_unique = {hit_key(item) for item in screened}
        new_screened = screened_unique - covered
        covered |= screened_unique
        if candidates:
            marginal.append({
                'pathway': f'db_boolean_{source}', 'pathway_type': 'db_boolean',
                'independence_class': 'source-level-partial', 'completed': True,
                'candidates': len(candidates), 'screened_high_confidence': 0,
                'screened_inclusions': len(screened_unique) if a.ai_provisional else 0,
                'new_high_confidence': 0,
                'new_screened_inclusions': len(new_screened) if a.ai_provisional else 0,
                'new_discovery_candidates': len(new_screened),
                'dedup_rule': 'stable identifier; title collision retained for manual review',
                'screening_status': first_run_status,
                'yield': round(len(new_screened) / len(candidates), 4),
                'note': 'Distinct database index, but still keyword-led; it is a provisional source-level B2 comparison, not an independent citation/standard pathway.'
            })

    out = pathlib.Path(a.out); out.mkdir(parents=True, exist_ok=True)
    json.dump(all_hits, open(out / 'query-hits.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
    potential_add.sort(key=lambda x: -x.get('cited_by_count', 0))
    json.dump({'first_round_discovery_rate': discovery_ggr,
               'discovery_candidate_count': len(potential_add),
               'included_high': 0,
               'ggr_status': 'not_assessable_until_screened',
               'additions': potential_add[:50]},
              open(out / 'potential_additions.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=2)

    # ── Build search_meta.json with v2 fields ──
    a2_evidence = "automated-screening" if a.ai_provisional else "measured"
    a2_note = 'A2 只有稳定 ID 匹配计入分子；分母=有稳定 ID 的 gold 条目（与 run_audit.a2 对齐）。'
    if validation_set:
        a2_note += f' 独立验证集: {val_total} 篇（{val_source}），dev/val 独立。'
        if val_total < 15:
            a2_note += ' 留出集少于 15 篇，首轮 recall 的抽样误差较大；应扩大候选锚点池后重跑。'
        if a.ai_provisional:
            a2_note += ' 本轮验证集由自动候选集机械留出，尚未完成外部来源与人工核验，因此仅作 automated-screening 初评。'
    else:
        a2_evidence = "estimated"
        a2_note += f' 无独立验证集——A2 使用 {dev_source}，可能被高估（dev=val 复用）。建议补充独立验证集。'

    json.dump({'queries': queries_record,
               # These are diagnostic query variants, not B saturation rounds.
               'diagnostic_query_rounds': search_rounds,
               'search_rounds': [],
               'saturation_rounds': [],
               # Source-level database routes are complete, but a credible
               # saturation workflow still needs non-keyword discovery routes.
               'planned_pathways': [row['pathway'] for row in marginal] + [
                   'backward_citation_seeded', 'forward_citation_seeded',
                   'related_articles_seeded', 'standards_guidelines_review'
               ],
               'diagnostic_pathway_yields': marginal,
               'a2': {'id_matched': a2_matched_id,
                      'title_candidates': a2_title_candidates,
                      'total_with_id': a2_total_with_id,
                      'total_all': a2_total_all,
                      'recall_by_id': a2_recall_id,
                      'id_matched_per_id_total': f'{a2_matched_id}/{a2_total_with_id}',
                      'missing_titles': a2_missing_titles[:15],
                      'note': a2_note,
                      'dev_id_diagnostics': dev_diagnostics,
                      'validation_id_diagnostics': validation_diagnostics},
               # v2 fields
               'dev_recall': dev_recall,
               'dev_recall_total': dev_total,
               'dev_source': dev_source,
               'validation_recall': val_recall,
               'validation_recall_total': val_total,
               'validation_source': val_source or '无独立验证集',
               'query_versions': [{'query_id': q.get('query_id'), 'origin': q.get('origin'),
                                   'query': q.get('query'), 'change_type': next((it['change_type'] for it in search_iterations if it['iteration_id'] == q.get('query_id')), 'initial'),
                                   'source': q.get('source'), 'execution_date': q.get('date'),
                                   'hits': q.get('hits'), 'status': q.get('status'),
                                   'execution_note': q.get('note')}
                                  for q in queries_record],
               'source_syntax_map': {source: SOURCE_SYNTAX[source] for source in sources},
               'search_iterations': search_iterations,
               'initial_query_origin': 'user_provided' if initial_query else 'ai_generated',
               'automatic_first_round': {
                   'status': 'diagnostic_bundle_complete',
                   'sources': sources,
                   'description': ('Multi-source q0 plus transparent atomic variants; title-level AI screening provides provisional B1 and source-level B2 diagnostics only.'
                                   if a.ai_provisional else 'Multi-source q0 plus transparent atomic variants; discovery candidates are not screened inclusions.'),
                   'b1_b2_b3_status': ('B1/B2=automated-screening; B3 reports process-started but cannot claim saturation without citation/standard pathways and independent validation.'
                                       if a.ai_provisional else 'not_assessable_until_screened_and_independent_pathway_runs'),
               },
               'a2_evidence_status': a2_evidence,
               'potential_additions_titles': [x['title'] for x in potential_add[:20]],
               'potential_additions_count': len(potential_add),
               'first_round_discovery_ggr': discovery_ggr,
               'note': '本输出只记录 q0→q* 的检索式诊断。固定稳健检索式的饱和度轮次需另行写入 saturation_rounds；B1/B2 不从每次关键词迭代计算。'},
              open(out / 'search_meta.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
    print(f'\n检索命中去重: {len(all_hits)} | A2 稳定ID: {a2_matched_id}/{a2_total_with_id}={a2_recall_id} | A2 标题候选: {a2_title_candidates}')
    if validation_set:
        print(f'Dev recall: {dev_recall} ({dev_total} 篇) | Validation recall: {val_recall} ({val_total} 篇) — {val_source}')
    else:
        print(f'Dev recall: {dev_recall} ({dev_total} 篇) — A2 证据状态: {a2_evidence}（无独立验证集）')
    print(f'Discovery 候选: {len(potential_add)} | included_high=0（待筛选确认）')


if __name__ == '__main__': main()
