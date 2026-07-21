#!/usr/bin/env python3
"""候选发现/诊断性检索器：构造代表性检索式 → 在线执行 → 产出 A2 的诊断命中、B 的 discovery candidates、潜在新增清单。

闭环：本脚本产出 → agent 把 search_rounds/queries 合并进 context.json → run_audit.py 计算 A2/B。
定位：减少 A2/B 的 missing-input 比例，而非自动得出 A2 结论或 B 饱和证据。
A2 只做稳定 ID 匹配（DOI/arXiv/OpenAlex ID），标题候选另存为人工核验参考。
B 的 included_high=0 直至人工筛选确认——discovery candidates ≠ 纳入项。

DRR 可复算性：source_marginal_yields 中每条路径附带 candidates（候选数）、
screened_high_confidence（高置信筛选数）、new_high_confidence（此前未发现的）和
dedup_rule（去重规则），供第三方从 query-hits.json 独立复算 yield。
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


def build_queries(keywords):
    """从关键词构造宽/中/窄梯度检索式。"""
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
    p.add_argument('--benchmark', help='A1 基准集 JSON；当 --gold 未提供时复用为 A2 gold set（需在 context 中标注 A1/A2 非独立，不能相互增强证据强度）')
    p.add_argument('--gold', help='A2 gold set JSON（独立于 A1 benchmark；若仅一组文献，应传给 --benchmark，并在 context 中标明 non-independent）')
    p.add_argument('--out', required=True)
    p.add_argument('--min-cited', type=int, default=10, help='潜在新增的 cited_by 下限')
    p.add_argument('--max-per-query', type=int, default=50,
                   help='每检索式最大命中数（仅首屏 top cited，非完整快照）')
    a = p.parse_args()

    library = json.load(open(a.library, encoding='utf-8'))
    ctx = json.load(open(a.context, encoding='utf-8'))
    gold = json.load(open(a.gold, encoding='utf-8')) if a.gold else (json.load(open(a.benchmark, encoding='utf-8')) if a.benchmark else [])
    gold_source = "gold独立" if a.gold else ("benchmark复用" if a.benchmark else "空")

    lib_dois = {(r.get('DOI') or '').lower() for r in library if r.get('DOI')}
    lib_arxivs = {r.get('arxiv') for r in library if r.get('arxiv')}
    lib_titles = {norm(r.get('title')) for r in library if r.get('title')}

    keywords = ctx.get('keywords', [])
    core_terms = [k.lower() for k in keywords
                  if any(x in k.lower() for x in ('gaussian', 'splatting', '3dgs'))]
    core_terms = core_terms or [k.lower() for k in keywords[:3]]
    queries = build_queries(keywords)
    print(f'构造 {len(queries)} 条检索式，核心词: {core_terms[:3]}')

    all_hits, seen, queries_record, potential_add = [], set(), [], []
    for label, q in queries:
        url = (f'https://api.openalex.org/works?search={urllib.parse.quote(q)}'
               f'&per-page={a.max_per_query}&sort=cited_by_count:desc&mailto=lit-eval@example.com')
        r = get(url)
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
                               'date': time.strftime('%Y-%m-%d'), 'hits': q_count})
        print(f'  [{label}] {q[:45]:45s} -> {q_count} 命中')
        time.sleep(0.3)

    # title 对齐：记录 gold 标题到命中记录的映射——仅作 A2 标题候选，
    # 绝不在命中的原始稳定 ID 上注入/改写任何 ID。
    # run_audit.a2() 只接受检索源原生返回的稳定 ID。
    gold_title_to_ids = {}
    for g in gold:
        nt = norm(g.get('title'))
        if nt:
            gids = set()
            for f in ('DOI', 'doi', 'arxiv', 'arXiv', 'pmid', 'PMID', 'openalex_id'):
                v = g.get(f) or ''
                if v: gids.add(v)
            if gids: gold_title_to_ids[nt] = gids

    # 标题候选匹配：gold-命中 title 交集（仅作跨体系人工核验参考，不计入 A2 分子）
    gold_titles = {norm(g.get('title')) for g in gold if g.get('title')}
    hit_titles = {norm(h.get('title')) for h in all_hits if h.get('title')}
    title_candidate_matches = gold_titles & hit_titles

    # 稳定 ID 匹配：仅用检索源原生返回的 DOI/arXiv 等已可追溯标识
    # （search_for_eval 不注入 ID——run_audit.a2 负责纯 ID 匹配）
    hit_ids = set()
    for h in all_hits:
        for f in ('DOI', 'doi', 'arxiv', 'arXiv', 'openalex_id'):
            v = h.get(f) or ''
            if v: hit_ids.add(v.lower())
    gold_ids = set()
    for g in gold:
        for f in ('DOI', 'doi', 'arxiv', 'arXiv', 'pmid', 'PMID', 'openalex_id'):
            v = g.get(f) or ''
            if v: gold_ids.add(v.lower())
    id_matched = gold_ids & hit_ids

    # A2 分母：仅计算有稳定 ID 的 gold 条目（与 run_audit.py 的 a2() 一致）
    # ——run_audit.a2() 用 ids() 函数提取 DOI/arXiv/PMID/PMCID/openalex_id 前缀
    gold_with_ids = [g for g in gold if isinstance(g, dict) and ids_for_gold(g)]
    a2_total_with_id = len(gold_with_ids)

    # A2 总分子 = 稳定 ID 匹配（不可混入标题候选）
    a2_matched_id = len(id_matched)
    a2_total_all = len(gold)  # 含无稳定 ID 的条目——用于信息完整性，不用于 Recall 分母
    a2_title_candidates = len(title_candidate_matches)
    a2_recall_id = round(a2_matched_id / a2_total_with_id, 3) if a2_total_with_id else None

    # 缺失——标题候选中有但 ID 未能匹配的
    a2_missing_titles = [g.get('title', '') for g in gold
                         if norm(g.get('title')) and norm(g.get('title')) not in hit_titles]

    # B 饱和度：发现候选（discovery candidates）与纳入项（included_high）的区分
    # 当前流程处于"候选发现"阶段，尚未完成筛选。发现候选不等于纳入——引用次数不能替代纳入决策。
    # GGR 分两个字段报告：
    #   discovery_ggr = 发现候选/库规模（当前已知可计算）
    #   included_high = 0（需全文/资格确认后才能填入，不能由自动检索器推定）
    lib_size = len(library)
    discovery_candidate_count = len(potential_add)
    # B1 的 included_high 在自动检索阶段设为 0——标记为 discovery_only
    # 只有经过筛选（标题摘要 → 全文 → 资格确认）后的新增纳入文献才能进入 GGR 分子。
    search_rounds = [{'pathway': 'openalex-first-round', 'completed': True,
                      'core_before': lib_size, 'included_high': 0,
                      'discovery_candidates': discovery_candidate_count,
                      'screening_status': 'discovery_only',
                      'note': '自动检索器产出的是发现候选（标题含核心词+cited_by≥阈值且不在库中），未经筛选不能计入 GGR 分子。GGR 分子=0 直至人工筛选确认。'}]
    discovery_ggr = round(discovery_candidate_count / lib_size, 4) if lib_size else None

    # 各检索式（路径）的边际收益 → DRR 原始输入（含候选数、初筛通过数、去重规则引用，
    # 供第三方从 query-hits.json 独立复算每个 yield）
    # 注意：当前阶段所有候选均为 screened_high_confidence=False（未做标题摘要筛选），
    # new_high_confidence 也是候选发现而非纳入——这会影响 DRR 的实际含义。
    covered = set(); marginal = []
    for qr in queries_record:
        label = qr['label']
        ph = [h for h in all_hits if h.get('query_label') == label]
        new_c = sum(1 for h in ph if norm(h['title']) not in covered)
        for h in ph: covered.add(norm(h['title']))
        if ph: marginal.append({
            'pathway': label,
            'candidates': len(ph),
            'screened_high_confidence': 0,  # discovery-only: screening not yet performed
            'new_high_confidence': 0,       # same — only screening yields real new_high_conf
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
                      'note': 'A2 只有稳定 ID 匹配计入分子；分母=有稳定 ID 的 gold 条目（与 run_audit.a2 对齐）。title_candidates 是跨体系人工核验参考，不属于 A2 实测召回。'},
               'potential_additions_titles': [x['title'] for x in potential_add[:20]],
               'potential_additions_count': len(potential_add),
               'first_round_discovery_ggr': discovery_ggr,
               'note': 'B 饱和度处于候选发现阶段——included_high=0 直至筛选确认。GGR 分子需人工完成纳入后方可填入。'},
              open(out / 'search_meta.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
    print(f'\n检索命中去重: {len(all_hits)} | A2 稳定ID: {a2_matched_id}/{a2_total_with_id}={a2_recall_id} | A2 标题候选: {a2_title_candidates}')
    print(f'Discovery 候选: {len(potential_add)} | included_high=0（待筛选确认）')


if __name__ == '__main__': main()
