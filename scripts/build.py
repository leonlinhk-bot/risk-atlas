#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Risk Atlas 数据构建脚本（无第三方依赖）

生成：
  1) data/index.json —— 列表页/搜索用的精简索引（去掉 body/body_en/body_hk/weekly_refs）
  2) data/graph.json —— 知识宇宙预计算图（nodes + links），避免前端加载全量正文再算边

用法：
  python3 scripts/build.py          # 生成（覆盖）
  python3 scripts/build.py --check  # 只校验生成物是否与当前一致（CI 用，过期则 exit 1）
"""
import json
import os
import re
import sys
import gzip

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENTRIES = os.path.join(ROOT, 'data', 'entries.json')
INDEX = os.path.join(ROOT, 'data', 'index.json')
GRAPH = os.path.join(ROOT, 'data', 'graph.json')

# 列表页/搜索所需字段白名单（正文与其他仅供 wiki 详情页使用的字段不进入 index.json）
BASE_FIELDS = ['slug', 'type', 'title', 'title_en', 'title_hk', 'en',
               'summary', 'summary_en', 'summary_hk', 'category', 'aliases']
EXTRA_FIELDS = {
    'course':     ['code', 'status', 'modules', 'modules_en', 'modules_hk', 'modules_note',
                   'workshop', 'pair', 'aiTools', 'source', 'number'],
    'concept':    ['code', 'courses'],
    'framework':  ['code', 'courses'],
    'track':      ['number', 'courses'],
    'credential': ['code', 'status', 'pair'],
    'job':        ['levels', 'salary_entry', 'salary_mid', 'salary_senior',
                   'credentials', 'employers', 'courses'],
    'employer':   ['site'],
    'channel':    ['source', 'code'],
    'resource':   ['source', 'code'],
    'tool':       ['verified'],
}
LINK_RE = re.compile(r'\[\[([^\]|]+)(?:\|[^\]]+)?\]\]')


def load_entries():
    with open(ENTRIES, encoding='utf-8') as f:
        return json.load(f)


def build_index(doc):
    out = []
    for e in doc['entries']:
        keep = BASE_FIELDS + EXTRA_FIELDS.get(e.get('type'), [])
        slim = {k: e[k] for k in keep if k in e and e[k] not in (None, '', [], {})}
        out.append(slim)
    return {
        'site': doc.get('site', {}),
        'generated_from': 'entries.json',
        'entries': out,
    }


def build_graph(doc):
    entries = doc['entries']
    have = {e['slug'] for e in entries}
    nodes = []
    for e in entries:
        nodes.append({
            'id': e['slug'],
            'type': e['type'],
            'title': e.get('title', ''),
            'title_en': e.get('title_en') or e.get('en') or '',
            'title_hk': e.get('title_hk') or e.get('title', ''),
            'en': e.get('en') or e.get('title_en') or '',
            'summary': e.get('summary', ''),
            'summary_en': e.get('summary_en') or e.get('summary', ''),
            'kind': e.get('kind'),
            'status': e.get('status'),
            'degree': 0,
        })
    pos = {n['id']: n for n in nodes}

    seen = set()
    links = []

    def add(a, b):
        if a == b or a not in have or b not in have:
            return
        key = (a, b) if a < b else (b, a)
        if key in seen:
            return
        seen.add(key)
        links.append({'source': a, 'target': b})

    for e in entries:
        for m in LINK_RE.finditer(e.get('body') or ''):
            add(e['slug'], m.group(1).strip())
    for e in entries:
        for c in (e.get('usedIn') or []):
            add(c, e['slug'])

    for l in links:
        pos[l['source']]['degree'] += 1
        pos[l['target']]['degree'] += 1

    return {'generated_from': 'entries.json', 'nodes': nodes, 'links': links}


def gz(data: bytes) -> int:
    return len(gzip.compress(data, 9))


def write_or_check(path, payload, check):
    text = json.dumps(payload, ensure_ascii=False, separators=(',', ':')) + '\n'
    data = text.encode('utf-8')
    old = None
    if os.path.exists(path):
        with open(path, 'rb') as f:
            old = f.read()
    changed = old != data
    if check:
        print(('  [过期] ' if changed else '  [一致] ') + os.path.relpath(path, ROOT))
        return changed
    if changed:
        with open(path, 'w', encoding='utf-8') as f:
            f.write(text)
    print(f"  {'已更新' if changed else '无变化'} {os.path.relpath(path, ROOT)}: "
          f"{len(data):,} B 原始 / {gz(data):,} B gzip")
    return changed


def main():
    check = '--check' in sys.argv
    doc = load_entries()
    with open(ENTRIES, 'rb') as f:
        raw = f.read()
    print(f"源: entries.json {len(raw):,} B 原始 / {gz(raw):,} B gzip | {len(doc['entries'])} 词条")
    stale = False
    stale |= write_or_check(INDEX, build_index(doc), check)
    stale |= write_or_check(GRAPH, build_graph(doc), check)
    if check and stale:
        print("✗ 生成物与 entries.json 不同步 —— 请运行 python3 scripts/build.py 并提交")
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
