#!/usr/bin/env python3
"""自主检索器：构造代表性检索式 → 在线执行 → 产出 A2 的 query-hits、B 的首轮 search_rounds、潜在新增清单。

闭环：本脚本产出 → agent 把 search_rounds/queries 合并进 context.json → run_audit.py 计算 A2/B。
解决"用户不留检索式"(A2)与"初次使用无多轮数据"(B)两个 not_assessable 痛点。

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
    p.add_argument('--benchmark', help='A1 锚点 JSON，复用为 A2 gold set')
    p.add_argument('--out', required=True)
    p.add_argument('--max-per-query', type=int, default=50)
    p.add_argument('--min-cited', type=int, default=10, help='潜在新增的 cited_by 下限')
    a = p.parse_args()

    library = json.load(open(a.library, encoding='utf-8'))
    ctx = json.load(open(a.context, encoding='utf-8'))
    gold = json.load(open(a.benchmark, encoding='utf-8')) if a.benchmark else []

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

    # title 对齐 hits 的 ID 到 gold 的 arXiv ID（跨体系，人工核验级；保持 run_audit.a2 纯 ID 匹配）
    gold_title_to_id = {}
    for g in gold:
        nt = norm(g.get('title'))
        if nt and g.get('arxiv'): gold_title_to_id[nt] = g['arxiv']
    for h in all_hits:
        nt = norm(h.get('title'))
        if nt in gold_title_to_id: h['arxiv'] = gold_title_to_id[nt]

    # A2 灵敏度：用 title 归一化匹配（gold 锚点与检索命中跨 ID 体系，title 最稳）
    gold_titles = {norm(g.get('title')) for g in gold if g.get('title')}
    hit_titles = {norm(h.get('title')) for h in all_hits if h.get('title')}
    a2_matched = len(gold_titles & hit_titles)
    a2_total = len(gold_titles)
    a2_recall = round(a2_matched / a2_total, 3) if a2_total else None
    a2_missing = [g.get('title', '') for g in gold if norm(g.get('title')) and norm(g.get('title')) not in hit_titles]

    # B 首轮 search_rounds
    lib_size = len(library)
    included_high = len(potential_add)
    search_rounds = [{'pathway': 'openalex-first-round', 'completed': True,
                      'core_before': lib_size, 'included_high': included_high}]
    ggr = round(included_high / lib_size, 4) if lib_size else None

    # 各检索式（路径）的边际收益 → DRR 原始输入（含候选数、筛选数、去重规则引用，
    # 供第三方从 query-hits.json 独立复算每个 yield）
    covered = set(); marginal = []
    for qr in queries_record:
        label = qr['label']
        ph = [h for h in all_hits if h.get('query_label') == label]
        new_c = sum(1 for h in ph if norm(h['title']) not in covered)
        for h in ph: covered.add(norm(h['title']))
        if ph: marginal.append({
            'pathway': label,
            'candidates': len(ph),
            'screened_high_confidence': len(ph),  # OpenAlex top-50 by cited — all considered high conf
            'new_high_confidence': new_c,
            'dedup_rule': 'title-normalized across all queries in this round',
            'yield': round(new_c / len(ph), 4)
        })

    out = pathlib.Path(a.out); out.mkdir(parents=True, exist_ok=True)
    json.dump(all_hits, open(out / 'query-hits.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
    potential_add.sort(key=lambda x: -x.get('cited_by_count', 0))
    json.dump({'first_round_ggr': ggr, 'potential_count': len(potential_add),
               'additions': potential_add[:50]},
              open(out / 'potential_additions.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
    json.dump({'queries': queries_record, 'search_rounds': search_rounds,
               'planned_pathways': ['openalex-first-round'],
               'source_marginal_yields': marginal,
               'a2': {'matched': a2_matched, 'total': a2_total, 'recall': a2_recall,
                      'missing_gold': a2_missing[:15]},
               'potential_additions_titles': [x['title'] for x in potential_add[:20]],
               'potential_additions_count': len(potential_add), 'first_round_ggr': ggr},
              open(out / 'search_meta.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
    print(f'\n检索命中去重: {len(all_hits)} | A2 灵敏度: {a2_matched}/{a2_total}={a2_recall}')
    print(f'潜在新增: {len(potential_add)} | 首轮 GGR: {included_high}/{lib_size}={ggr}')


if __name__ == '__main__': main()
