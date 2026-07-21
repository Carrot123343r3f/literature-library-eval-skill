#!/usr/bin/env python3
"""候选发现/诊断性检索器：构造代表性检索式 → 在线执行 → 产出 A2 的诊断命中、B 的 discovery candidates、潜在新增清单。

闭环：本脚本产出 → agent 把 search_rounds/queries 合并进 context.json → run_audit.py 计算 A2/B。
定位：减少 A2/B 的 missing-input 比例，而非自动得出 A2 结论或 B 饱和证据。
A2 只做稳定 ID 匹配（DOI/arXiv/OpenAlex ID），标题候选另存为人工核验参考。
B 的 included_high=0 直至人工筛选确认——discovery candidates ≠ 纳入项。

Dev/validation set separation（v2）：
  --dev-set 指定开发集（用于迭代反馈），--validation-set 指定独立验证集（用于最终 A2 判定）。
  两个集合不应有重叠。若只提供 --benchmark，整套作为 dev_set 使用，validation_set 为空，
  A2 将标注为 estimated 证据状态。
  独立验证集不参与检索式迭代——一旦用于调整检索式，就"烧掉"了独立性。

DRR 可复算性：source_marginal_yields 中每条路径附带 candidates（候选数）、
screened_high_confidence（高置信筛选数）、new_high_confidence（此前未发现的）和
dedup_rule（去重规则），供第三方从 query-hits.json 独立复算 yield。

工程 PICO 分解（v2）：
  接受 --pico 参数（JSON 文件），内含 object/technology/performance/context 四要素分解。
  用于指导多源异构语法映射——每个来源选择其支持的字段语法，不把同一字符串原样投到不同数据库。
"""
import argparse, json, urllib.request, urllib.parse, re, time, sys, pathlib
sys.stdout.reconfigure(encoding='utf-8')


def get(url, t=5):
    for i in range(t):
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'lit-eval'})
            return json.load(urllib.request.urlopen(req, timeout=30))
        except Exception as e:
            if i == t-1: return {'error': str(e)}
            time.sleep(2)


def arxiv_from_doi(doi):
    if doi and '10.48550/arXiv' in str(doi):
        m = re.search(r'arXiv\.(\d{4}\.\d{4,5})', str(doi))
        return m.group(1) if m else None
    return None


def norm(t):
    return re.sub(r'[^a-z0-9]', '', str(t or '').lower())

def ids_for_gold(g):
    """Extract stable IDs from a gold entry — same logic as run_audit.ids()."""
    found = set()
    doi_match = re.search(r"(10\.\d{4,9}/\S+)", str(g.get("DOI") or g.get("doi") or ""), re.I)
    if doi_match: found.add("doi:" + doi_match.group(1).rstrip(".,;:)]}").lower())
    for key, prefix in (("PMID", "pmid"), ("pmid", "pmid"), ("PMCID", "pmcid"),
                        ("arxiv", "arxiv"), ("arXiv", "arxiv"), ("openalex_id", "openalex")):
        if g.get(key): found.add(prefix + ":" + str(g[key]).casefold())
    raw = str(g.get("id") or "").casefold()
    if raw.startswith(("pmid:", "pmcid:", "arxiv:", "openalex:")): found.add(raw)
    return found

def entry_ids(entry):
    """Extract stable IDs from a query hit entry."""
    found = set()
    doi = (entry.get('doi') or '').replace('https://doi.org/', '').lower()
    if doi: found.add('doi:' + doi)
    ax = arxiv_from_doi(entry.get('doi'))
    if ax: found.add('arxiv:' + ax)
    oaid = entry.get('id') or entry.get('openalex_id') or ''
    if oaid: found.add(oaid.lower())
    return found

def compute_recall(gold_set, hit_ids_set):
    """Compute recall at item level. Each gold item matched if any stable ID overlaps."""
    gold_with_ids = [g for g in gold_set if isinstance(g, dict) and ids_for_gold(g)]
    if not gold_with_ids:
        return None, 0
    matched = sum(1 for g in gold_with_ids if ids_for_gold(g) & hit_ids_set)
    return round(matched / len(gold_with_ids), 3), len(gold_with_ids)

def build_queries(keywords, pico=None):
    """从关键词构造宽/中/窄梯度检索式。若提供 PICO 分解，多源异构语法映射。

    PICO 格式：{"object": {...}, "technology": {...},
                "performance": {...}, "context": {...},
                "supplements": [...]}
    若 pico 不为空：使用 PICO 要素构建检索式而非原始 keywords。
    """
    if pico and isinstance(pico, dict):
        # Build from PICO decomposition
        core = [pico.get("object", {}).get("term", ""), pico.get("technology", {}).get("term", "")]
        core = [c for c in core if c]
        if not core:
            return build_queries(keywords)  # fallback to keywords
        primary = core[0].split(";")[0].strip()
        queries = [('宽', f'"{primary}"')]
        for term in core:
            for t in term.split(";"):
                t = t.strip()
                if t and norm(t) not in {norm(q[1].replace('"','')) for q in queries}:
                    queries.append(('中', f'"{primary}" {t}'))
                    break
            if len(queries) >= 4:
                break
        queries.append(('窄(title)', f'title:"{primary}"'))
        return queries[:5]

    # Original keyword-based building
    if not keywords:
        return []
    core = keywords[0]
    queries = [('宽', f'"{core}"')]
    seen_sub = {norm(core)}
    for sub in keywords[1:5]:
        if norm(sub) not in seen_sub:
            queries.append(('中', f'"{core}" {sub}'))
            seen_sub.add(norm(sub))
        if len(queries) >= 4: break
    queries.append(('窄(title)', f'title:"{core}"'))
    return queries[:5]


def main():
    p = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    p.add_argument('--library', required=True, help='题录 JSON（判断在库内）')
    p.add_argument('--context', required=True, help='context.json（读 keywords/profile）')
    p.add_argument('--benchmark', help='A1 基准集 JSON；当 --dev-set 和 --gold 均未提供时复用为 dev_set')
    p.add_argument('--gold', help='A2 gold set JSON（若需要独立于 benchmark；v2 建议使用 --dev-set + --validation-set）')
    p.add_argument('--dev-set', help='[v2] 开发集 JSON — 用于迭代检索式（多次使用）')
    p.add_argument('--validation-set', help='[v2] 独立验证集 JSON — 仅用于最终 A2 判定（看过即"烧掉"，不用于调检索式）')
    p.add_argument('--pico', help='[v2] 工程 PICO 分解 JSON — object/technology/performance/context')
    p.add_argument('--out', required=True)
    p.add_argument('--min-cited', type=int, default=10, help='潜在新增的 cited_by 下限')
    p.add_argument('--max-per-query', type=int, default=50,
                   help='每检索式最大命中数（仅首屏 top cited，非完整快照）')
    a = p.parse_args()

    library = json.load(open(a.library, encoding='utf-8'))
    ctx = json.load(open(a.context, encoding='utf-8'))

    # ── Dev/validation set resolution (v2) ──
    dev_set = validation_set = None
    dev_source = val_source = ""

    if a.dev_set:
        dev_set = json.load(open(a.dev_set, encoding='utf-8'))
        dev_set = dev_set if isinstance(dev_set, list) else dev_set.get("items", [])
        dev_source = "独立 dev-set 文件"
    elif a.gold:
        dev_set = json.load(open(a.gold, encoding='utf-8'))
        dev_set = dev_set if isinstance(dev_set, list) else dev_set.get("items", [])
        dev_source = "gold set (无独立验证集)"
    elif a.benchmark:
        dev_set = json.load(open(a.benchmark, encoding='utf-8'))
        dev_set = dev_set if isinstance(dev_set, list) else dev_set.get("items", [])
        dev_source = "benchmark (无独立验证集)"

    if a.validation_set:
        validation_set = json.load(open(a.validation_set, encoding='utf-8'))
        validation_set = validation_set if isinstance(validation_set, list) else validation_set.get("items", [])
        val_source = "独立验证集"
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
        pico = json.load(open(a.pico, encoding='utf-8'))

    lib_dois = {(r.get('DOI') or '').lower() for r in library if r.get('DOI')}
    lib_arxivs = {r.get('arxiv') for r in library if r.get('arxiv')}
    lib_titles = {norm(r.get('title')) for r in library if r.get('title')}

    keywords = ctx.get('keywords', [])
    core_terms = [k.lower() for k in keywords[:3]]
    queries = build_queries(keywords, pico)
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

    all_hits, seen, queries_record, potential_add = [], set(), [], []
    for label, q in queries:
        url = (f'https://api.openalex.org/works?search={urllib.parse.quote(q)}'
               f'&per-page={a.max_per_query}&sort=cited_by_count:desc&mailto=lit-eval@example.com')
        r = get(url)
        status = "complete"
        if isinstance(r, dict) and r.get("error"):
            status = "failed"
            r = {"results": []}
        hits = r.get('results', []) if isinstance(r, dict) else []
        q_count = 0
        for w in hits:
            doi = (w.get('doi') or '').replace('https://doi.org/', '').lower()
            ax = arxiv_from_doi(w.get('doi'))
            title = w.get('title', '') or ''
            cited = w.get('cited_by_count', 0) or 0
            k = doi or ax or norm(title)
            if not k or k in seen: continue
            seen.add(k)
            item = {'DOI': doi, 'arxiv': ax or '', 'title': title,
                    'openalex_id': w.get('id', ''),
                    'cited_by_count': cited, 'year': w.get('publication_year'),
                    'query_label': label}
            all_hits.append(item); q_count += 1
            in_lib = (doi and doi in lib_dois) or (ax and ax in lib_arxivs) or (norm(title) in lib_titles)
            if not in_lib:
                tl = title.lower()
                if any(term in tl for term in core_terms) and cited >= a.min_cited:
                    potential_add.append(item)
        queries_record.append({'source': 'OpenAlex', 'query': q, 'label': label,
                               'date': time.strftime('%Y-%m-%d'), 'hits': q_count,
                               'status': status,
                               'note': 'failed' if status == 'failed' else 'top-cited-only'})
        print(f'  [{label}] {q[:45]:45s} -> {q_count} 命中')
        time.sleep(0.3)

    # ── Build hit ID set for recall computation ──
    hit_ids_set = set()
    for h in all_hits:
        hit_ids_set |= entry_ids(h)

    # ── Compute dev_recall + validation_recall ──
    dev_recall, dev_total = compute_recall(dev_set, hit_ids_set) if dev_set else (None, 0)
    val_recall, val_total = compute_recall(validation_set, hit_ids_set) if validation_set else (None, 0)

    # ── A2: evaluate against gold/dev_set for backward compat ──
    gold = dev_set or []  # default gold = dev_set
    gold_ids = set()
    for g in gold:
        gold_ids |= ids_for_gold(g)
    id_matched = gold_ids & hit_ids_set
    gold_with_ids = [g for g in gold if isinstance(g, dict) and ids_for_gold(g)]
    a2_total_with_id = len(gold_with_ids)
    a2_matched_id = len(id_matched)
    a2_total_all = len(gold)
    a2_recall_id = round(a2_matched_id / a2_total_with_id, 3) if a2_total_with_id else None

    # Title candidate matching for cross-system manual verification
    gold_titles = {norm(g.get('title')) for g in gold if g.get('title')}
    hit_titles = {norm(h.get('title')) for h in all_hits if h.get('title')}
    title_candidate_matches = gold_titles & hit_titles
    a2_title_candidates = len(title_candidate_matches)
    a2_missing_titles = [g.get('title', '') for g in gold
                         if norm(g.get('title')) and norm(g.get('title')) not in hit_titles]

    # ── B saturation ──
    lib_size = len(library)
    discovery_candidate_count = len(potential_add)
    search_rounds = [{'pathway': 'openalex-first-round', 'completed': True,
                      'core_before': lib_size, 'included_high': 0,
                      'discovery_candidates': discovery_candidate_count,
                      'screening_status': 'discovery_only',
                      'note': '自动检索器产出的是发现候选（标题含核心词+cited_by≥阈值且不在库中），未经筛选不能计入 GGR 分子。GGR 分子=0 直至人工筛选确认。'}]
    discovery_ggr = round(discovery_candidate_count / lib_size, 4) if lib_size else None

    # Marginal yields per query
    covered = set(); marginal = []
    for qr in queries_record:
        label = qr['label']
        ph = [h for h in all_hits if h.get('query_label') == label]
        new_c = sum(1 for h in ph if norm(h['title']) not in covered)
        for h in ph: covered.add(norm(h['title']))
        if ph: marginal.append({
            'pathway': label,
            'candidates': len(ph),
            'screened_high_confidence': 0,
            'new_high_confidence': 0,
            'new_discovery_candidates': new_c,
            'dedup_rule': 'title-normalized across all queries in this round',
            'screening_status': 'discovery_only',
            'yield': round(new_c / len(ph), 4)
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
    a2_evidence = "measured"
    a2_note = 'A2 只有稳定 ID 匹配计入分子；分母=有稳定 ID 的 gold 条目（与 run_audit.a2 对齐）。'
    if validation_set:
        a2_note += f' 独立验证集: {val_total} 篇（{val_source}），dev/val 独立。'
    else:
        a2_evidence = "estimated"
        a2_note += f' 无独立验证集——A2 使用 {dev_source}，可能被高估（dev=val 复用）。建议补充独立验证集。'

    json.dump({'queries': queries_record, 'search_rounds': search_rounds,
               'planned_pathways': ['openalex-first-round'],
               'source_marginal_yields': marginal,
               'a2': {'id_matched': a2_matched_id,
                      'title_candidates': a2_title_candidates,
                      'total_with_id': a2_total_with_id,
                      'total_all': a2_total_all,
                      'recall_by_id': a2_recall_id,
                      'id_matched_per_id_total': f'{a2_matched_id}/{a2_total_with_id}',
                      'missing_titles': a2_missing_titles[:15],
                      'note': a2_note},
               # v2 fields
               'dev_recall': dev_recall,
               'dev_recall_total': dev_total,
               'dev_source': dev_source,
               'validation_recall': val_recall,
               'validation_recall_total': val_total,
               'validation_source': val_source or '无独立验证集',
               'a2_evidence_status': a2_evidence,
               'potential_additions_titles': [x['title'] for x in potential_add[:20]],
               'potential_additions_count': len(potential_add),
               'first_round_discovery_ggr': discovery_ggr,
               'note': 'B 饱和度处于候选发现阶段——included_high=0 直至筛选确认。GGR 分子需人工完成纳入后方可填入。'},
              open(out / 'search_meta.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
    print(f'\n检索命中去重: {len(all_hits)} | A2 稳定ID: {a2_matched_id}/{a2_total_with_id}={a2_recall_id} | A2 标题候选: {a2_title_candidates}')
    if validation_set:
        print(f'Dev recall: {dev_recall} ({dev_total} 篇) | Validation recall: {val_recall} ({val_total} 篇) — {val_source}')
    else:
        print(f'Dev recall: {dev_recall} ({dev_total} 篇) — A2 证据状态: {a2_evidence}（无独立验证集）')
    print(f'Discovery 候选: {len(potential_add)} | included_high=0（待筛选确认）')


if __name__ == '__main__': main()
