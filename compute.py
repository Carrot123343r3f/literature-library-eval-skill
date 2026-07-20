#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
文献综述库质量评估 — 指标计算脚本（literature-library-eval skill 配套）
用法:
  python compute.py --lib zotero --userid 20959985 --apikey XXX \
                    --benchmark bench.json --anchor-wid W4385318467 \
                    --domain-keyword "gaussian splatting"
  python compute.py --lib json --jsonfile lib.json
输出: JSON（各指标值），供 AI 填入评估报告
依赖: pyzotero（读 Zotero 时）、httpx 或 urllib（OpenAlex）
"""
import argparse, json, re, statistics, math, urllib.request
from collections import Counter
from urllib.parse import quote


def norm_title(t):
    """标题归一化，仅用于生成待人工核验候选，不能替代稳定标识符匹配。"""
    return re.sub(r'[^\w]', '', (t or '').casefold())


def norm_doi(value):
    """提取并规范 DOI；返回空字符串表示未发现。"""
    m = re.search(r'(?:doi:\s*|https?://(?:dx\.)?doi\.org/)?(10\.\d{4,9}/\S+)',
                  value or '', flags=re.I)
    return m.group(1).rstrip('.,;:)]}').lower() if m else ''


def record_ids(record):
    """从常见 Zotero/JSON 字段收集稳定标识符。"""
    ids = set()
    for field in ('DOI', 'doi'):
        doi = norm_doi(str(record.get(field) or ''))
        if doi:
            ids.add(f'doi:{doi}')
    extra = str(record.get('extra') or '')
    doi = norm_doi(extra)
    if doi:
        ids.add(f'doi:{doi}')
    for field, prefix in (('PMID', 'pmid'), ('pmid', 'pmid'),
                          ('arxiv', 'arxiv'), ('arXiv', 'arxiv'),
                          ('openalex_id', 'openalex')):
        value = str(record.get(field) or '').strip()
        if value:
            ids.add(f'{prefix}:{value.casefold()}')
    return ids


# ---------- 数据加载 ----------
def load_zotero(userid, apikey):
    from pyzotero import zotero
    zot = zotero.Zotero(userid, 'user', apikey)
    items = zot.everything(zot.top())
    return [i['data'] for i in items
            if i['data'].get('itemType') not in ('attachment', 'note', 'annotation')]


def load_json(path):
    return json.load(open(path, encoding='utf-8'))


# ---------- A 覆盖度 ----------
def benchmark_recall(lib, benchmark):
    """A1：对有稳定标识符的基准集做实测；标题仅产生待核验候选。"""
    items = benchmark.get('items', []) if isinstance(benchmark, dict) else benchmark
    lib_ids = set().union(*(record_ids(d) for d in lib)) if lib else set()
    lib_titles = {norm_title(d.get('title')) for d in lib if d.get('title')}
    stable_items = [d for d in items if isinstance(d, dict) and record_ids(d)]
    title_only = [d for d in items if not isinstance(d, dict) or not record_ids(d)]
    matched = sum(1 for d in stable_items if record_ids(d) & lib_ids)
    candidates = []
    for d in title_only:
        title = d if isinstance(d, str) else d.get('title', '')
        if norm_title(title) in lib_titles:
            candidates.append(title)
    result = {
        'evidence_status': 'measured' if stable_items else 'not_assessable',
        'stable_id_total': len(stable_items),
        'stable_id_matched': matched,
        'recall': round(matched / len(stable_items), 3) if stable_items else None,
        'title_only_candidates_for_manual_review': candidates,
    }
    if title_only:
        result['note'] = ('标题候选不计入召回率；请补 DOI/PMID/arXiv ID 或人工确认。')
    return result


def openalex_candidate_count(wid, search, mailto='research@example.com'):
    """查询候选集规模；它不是 Recall 分母。"""
    url = (f"https://api.openalex.org/works?filter=cites:{wid}"
           f"&search={quote(search)}&per_page=1&mailto={mailto}")
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        return json.loads(urllib.request.urlopen(req, timeout=30).read())['meta']['count']
    except Exception as ex:
        return {'error': str(ex)[:80]}


# ---------- C 均衡 ----------
def cv_gini(counts):
    """C1: 各子方向篇数的 CV 与 Gini"""
    n = len(counts)
    if n == 0:
        return None
    m = statistics.mean(counts)
    cv = statistics.pstdev(counts) / m if m else 0
    s = sorted(counts); cum = sum(s)
    gini = sum((2 * (i + 1) - n - 1) * x for i, x in enumerate(s)) / (n * cum) if cum else 0
    return {'cv': round(cv, 3), 'gini': round(gini, 3)}


def shannon_normalized(proportions):
    """C2: Shannon熵 H 与归一化 J=H/ln(n)"""
    H = -sum(p * math.log(p) for p in proportions if p > 0)
    n = len([p for p in proportions if p > 0])
    J = H / math.log(n) if n > 1 else 0
    return {'H': round(H, 3), 'J': round(J, 3)}


# ---------- D 质量 ----------
def h_core(citations):
    """D1: h-index 风格，库内至少 h 篇被引≥h"""
    s = sorted((c for c in citations if c is not None), reverse=True)
    h = 0
    for i, c in enumerate(s, 1):
        if c >= i:
            h = i
        else:
            break
    return h


# ---------- F 时效 ----------
def recency(years, N=2, current_year=2026):
    """F1: 近 N 年占比"""
    valid = [y for y in years if y]
    if not valid:
        return None
    recent = sum(1 for y in valid if y >= current_year - N + 1)
    return round(recent / len(valid), 3)


# ---------- B 饱和（需多轮检索日志，这里只给工具函数）----------
def snowballing_gain(new_unique, cumulative_total):
    """B1: GGR = 本轮unique新增 / 累计库"""
    return round(new_unique / cumulative_total, 3) if cumulative_total else None


def duplicate_rate(in_lib_this_round, total_this_round):
    """B2: DRR = 本轮已入库 / 本轮总数"""
    return round(in_lib_this_round / total_this_round, 3) if total_this_round else None


# ---------- E 可用 ----------
def abstract_rate(lib):
    n = len(lib)
    return round(sum(1 for d in lib if (d.get('abstractNote') or '').strip()) / n, 3) if n else None


def fulltext_rate(lib, pdf_field='extra', marker='本地PDF'):
    """E2: 库内 extra 字段含本地PDF路径的比例"""
    n = len(lib)
    return round(sum(1 for d in lib if marker in (d.get(pdf_field) or '')) / n, 3) if n else None


# ---------- 主入口 ----------
def main():
    ap = argparse.ArgumentParser(description='文献库质量评估指标计算')
    ap.add_argument('--lib', choices=['zotero', 'json'], required=True)
    ap.add_argument('--jsonfile')
    ap.add_argument('--userid'); ap.add_argument('--apikey')
    ap.add_argument('--benchmark', help='JSON: 基准集列表；推荐 records（含 DOI/PMID/arXiv ID）')
    ap.add_argument('--anchor-wid', default='W4385318467', help='OpenAlex 锚点论文 WID')
    ap.add_argument('--candidate-query', '--domain-keyword', dest='candidate_query',
                    help='候选集检索关键词；只输出查询规模，不计算 Recall')
    ap.add_argument('--recency-n', type=int, default=2)
    args = ap.parse_args()

    lib = load_zotero(args.userid, args.apikey) if args.lib == 'zotero' else load_json(args.jsonfile)
    N = len(lib)
    years = []
    for d in lib:
        m = re.search(r'(20\d{2})', d.get('date') or '')
        if m:
            years.append(int(m.group(1)))

    res = {'N': N}
    # A 覆盖
    if args.benchmark:
        bt = json.load(open(args.benchmark, encoding='utf-8'))
        res['benchmark_recall'] = benchmark_recall(lib, bt)
    if args.candidate_query:
        dc = openalex_candidate_count(args.anchor_wid, args.candidate_query)
        res['candidate_pool'] = {
            'source': 'OpenAlex cites+search',
            'query': args.candidate_query,
            'count': dc,
            'evidence_status': 'estimate',
            'note': ('单源查询规模不是 Recall 分母；需多源去重、查询快照和明确纳入标准后才可做覆盖估计。'),
        }
    # C 均衡（子方向篇数需外部给，这里输出年份/来源分布供参考）
    res['year_dist'] = dict(Counter(years).most_common(6))
    # F 时效
    res['recency'] = recency(years, args.recency_n)
    # E 可用
    res['abstract_rate'] = abstract_rate(lib)
    res['fulltext_rate'] = fulltext_rate(lib)
    # 说明
    res['_note'] = ('A1 仅对稳定标识符基准集输出实测召回；A2 需查询快照与 gold set；A3 只可报告覆盖估计。'
                    'C1/C2/D1 需子方向篇数/venue分布/被引数，请用相应数据源补齐。')
    print(json.dumps(res, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
