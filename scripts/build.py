#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Risk Atlas 数据构建脚本（无第三方依赖）

生成：
  1) data/index.json —— 列表页/搜索用的精简索引（去掉 body/body_en/body_hk/weekly_refs）
  2) data/graph.json —— 知识宇宙预计算图（nodes + links），避免前端加载全量正文再算边
  3) data/entry/<slug>.json —— 词条详情页分片（该词条全文 + 预计算反向链接），
     取代「详情页下载整份 14 MB entries.json」的做法

用法：
  python3 scripts/build.py          # 生成（覆盖；分片按内容变化增量写，并清理已删词条的分片）
  python3 scripts/build.py --check  # 只校验生成物是否与当前一致（CI 用，过期则 exit 1）
"""
import datetime
import json
import os
import re
import sys
import gzip

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENTRIES = os.path.join(ROOT, 'data', 'entries.json')
INDEX = os.path.join(ROOT, 'data', 'index.json')
GRAPH = os.path.join(ROOT, 'data', 'graph.json')
ENTRY_DIR = os.path.join(ROOT, 'data', 'entry')   # 词条分片目录
# 语言化派生文件（每次只加载当前语言，体积约为合并版 1/3）
LANG_OUT = {
    'zh-cn': ('data/index.json', 'data/graph.json'),          # 同时作为向后兼容的默认文件
    'en':    ('data/index.en.json', 'data/graph.en.json'),
    'hk':    ('data/index.hk.json', 'data/graph.hk.json'),
}
# 搜索语料（懒加载用；取代整份 entries.json）：短键压缩字段名
SEARCH_OUT = {'zh-cn': 'data/search.json', 'en': 'data/search.en.json', 'hk': 'data/search.hk.json'}
# 标题映射（详情页解析双链显示名/反链标签用；比整份 index 小得多）
TITLES_OUT = {'zh-cn': 'data/titles.json', 'en': 'data/titles.en.json', 'hk': 'data/titles.hk.json'}
BODY_EXCERPT = 80    # 正文摘录字符数（正文全文仍在 entries.json / 词条页）
SITEMAP = os.path.join(ROOT, 'sitemap.xml')
SITE = 'https://risk-atlas.wiki'
STATIC_PATHS = ['/', '/weekly.html', '/catalog.html', '/career.html',
                '/companies.html', '/map.html', '/categories.html']

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
# 带「别名」捕获组的版本（清洗摘要时需要拿到 [[slug|别名]] 里的别名）
LINK_LABEL_RE = re.compile(r'\[\[([^\]|]+)(?:\|([^\]]+))?\]\]')


# 列表页展示用的文本截断上限（正文仍在 entries.json / wiki 详情页，不受影响）
TRUNC = {'title': 90, 'title_en': 90, 'title_hk': 90,
         'summary': 120, 'summary_en': 120, 'summary_hk': 120}
GRAPH_TRUNC = {'title': 90, 'title_en': 90, 'title_hk': 90,
               'summary': 110, 'summary_en': 110}
# 每种语言的派生文件只保留「该语言的标题/摘要 + en」，砍掉另外两种语言，体积约 1/3
LANG_FIELDS = {
    'zh-cn': {'title': 'title', 'summary': 'summary'},
    'en':    {'title': 'title_en', 'summary': 'summary_en'},
    'hk':    {'title': 'title_hk', 'summary': 'summary_hk'},
}


def clean_title(s, n=60):
    t = re.sub(r'\*\*|__|`', '', str(s or ''))
    t = re.sub(r'\s+', ' ', t).strip()
    return clip(t, n)


def clean_md(s, resolve=None):
    """列表卡片用的摘要清洗：剥 markdown 标记 + 把 [[slug|label]] 解析成可读文本。
    卡片不渲染 markdown，原样输出会显示成 **、` 这类符号（实测 index 中 197 条中招）。"""
    t = str(s or '')

    def rep(m):
        slug = m.group(1).strip()
        label = (m.group(2) or '').strip()
        if label:
            return label
        return (resolve or {}).get(slug, slug)

    t = LINK_LABEL_RE.sub(rep, t)
    t = re.sub(r'\*\*|__|`', '', t)
    return re.sub(r'\s+', ' ', t).strip()


def clip(s, n):
    if not isinstance(s, str) or len(s) <= n:
        return s
    return s[:n - 1].rstrip() + '…'


def load_entries():
    with open(ENTRIES, encoding='utf-8') as f:
        return json.load(f)


def build_index(doc, lang='zh-cn'):
    out = []
    tf, sf = LANG_FIELDS[lang]['title'], LANG_FIELDS[lang]['summary']
    # 摘要里可能含 [[slug]]，解析成该语言下的标题（构建期一次算好）
    resolve = {}
    for e in doc['entries']:
        resolve[e['slug']] = clean_title(e.get(tf) or e.get('title') or '', 40)
    drop = set()
    for k, v in LANG_FIELDS.items():
        if k == lang:
            continue
        drop.add(v['title'])
        drop.add(v['summary'])
    for e in doc['entries']:
        keep = BASE_FIELDS + EXTRA_FIELDS.get(e.get('type'), [])
        slim = {k: e[k] for k in keep if k in e and e[k] not in (None, '', [], {})}
        for f in list(slim.keys()):
            if f in drop:
                del slim[f]
        # 把当前语言的标题/摘要同时写入 title/summary（页面与搜索直接消费这两个字段）
        if lang != 'zh-cn':
            t = e.get(tf) or e.get('title') or ''
            sm = e.get(sf) or e.get('summary') or ''
            if t:
                slim['title'] = t
            if sm:
                slim['summary'] = sm
        for f in ('summary', 'summary_en', 'summary_hk'):
            if f in slim:
                slim[f] = clean_md(slim[f], resolve)
        for f, n in TRUNC.items():
            if f in slim:
                slim[f] = clip(slim[f], n)
        out.append(slim)
    return {
        'site': doc.get('site', {}),
        'generated_from': 'entries.json',
        'entries': out,
    }


def build_graph(doc, lang='zh-cn'):
    entries = doc['entries']
    tfield = LANG_FIELDS[lang]['title']
    sfield = LANG_FIELDS[lang]['summary']
    resolve = {e['slug']: clean_title(e.get(tfield) or e.get('title') or '', 40) for e in entries}
    have = {e['slug'] for e in entries}
    nodes = []
    for e in entries:
        nodes.append({
            'id': e['slug'],
            'type': e['type'],
            'title': clean_title(e.get(tfield) or e.get('title') or '', 60),
            'en': clip(e.get('en') or e.get('title_en') or '', GRAPH_TRUNC['title_en']),
            'summary': clip(clean_md(e.get(sfield) or e.get('summary') or '', resolve), GRAPH_TRUNC['summary']),
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


def build_titles(doc, lang='zh-cn'):
    """标题映射：复用 build_index 的语言解析与截断结果，保证与列表页显示完全一致。
    结构 {slug: [title, type]}——详情页只需它来渲染双链显示名、反链标签与信息栏。"""
    idx = build_index(doc, lang)
    entries = {}
    for e in idx['entries']:
        entries[e['slug']] = [e.get('title', ''), e.get('type', '')]
    return {'generated_from': 'entries.json', 'lang': lang, 'entries': entries}


def outgoing_slugs(e):
    """与 js/wiki.js 的 outgoingSlugs() 逐条对齐（分片里的反链必须与前端算法一致）"""
    found = set()
    for m in LINK_RE.finditer(e.get('body') or ''):
        found.add(m.group(1).strip())
    for t in (e.get('aiTools') or []):
        mm = re.match(r'^\[\[([^\]|]+)', str(t))
        if mm:
            found.add(mm.group(1).strip())
    for k in ('concepts', 'courses', 'usedIn', 'credentials', 'employers'):
        for s in (e.get(k) or []):
            found.add(str(s).strip())
    if e.get('pair'):
        found.add(str(e['pair']).strip())
    tr = e.get('track')
    if tr:
        if isinstance(tr, dict):
            if tr.get('slug'):
                found.add(str(tr['slug']).strip())
        else:
            found.add(str(tr).strip())
    return found


def build_backlink_map(entries):
    """slug -> 入链来源 slug 列表（保持 entries.json 顺序，与前端 Wiki.backlinks 一致）"""
    have = {e['slug'] for e in entries}
    rev = {}
    for e in entries:
        for t in outgoing_slugs(e):
            if t in have and t != e['slug']:
                rev.setdefault(t, [])
                if e['slug'] not in rev[t]:
                    rev[t].append(e['slug'])
    return rev


def build_entry_shards(doc):
    """词条分片：{"e": <完整词条>, "b": [入链 slug]}（短键省字节）"""
    entries = doc['entries']
    back = build_backlink_map(entries)
    shards = {}
    for e in entries:
        payload = {'e': e, 'b': back.get(e['slug'], [])}
        shards[e['slug']] = json.dumps(payload, ensure_ascii=False, separators=(',', ':')) + '\n'
    return shards


def write_shards_or_check(shards, check):
    """按内容增量写分片，并清理已不存在词条的分片"""
    os.makedirs(ENTRY_DIR, exist_ok=True)
    stale = False
    written = kept = 0
    total_bytes = 0
    for slug, text in shards.items():
        path = os.path.join(ENTRY_DIR, slug + '.json')
        data = text.encode('utf-8')
        total_bytes += len(data)
        old = None
        if os.path.exists(path):
            with open(path, 'rb') as f:
                old = f.read()
        if old == data:
            kept += 1
            continue
        stale = True
        if not check:
            with open(path, 'w', encoding='utf-8') as f:
                f.write(text)
            written += 1
    # 已删除词条的分片
    expect = {s + '.json' for s in shards}
    removed = 0
    for fn in os.listdir(ENTRY_DIR):
        if fn.endswith('.json') and fn not in expect:
            stale = True
            if not check:
                os.remove(os.path.join(ENTRY_DIR, fn))
                removed += 1
    if check:
        flag = '[过期] ' if stale else '[一致] '
        print(f"  {flag}data/entry/: {len(shards)} 个分片，{total_bytes:,} B 原始")
        return stale
    parts = [f"{written} 个写入"] if written else []
    if removed:
        parts.append(f"{removed} 个已删词条分片清理")
    if kept:
        parts.append(f"{kept} 个未变")
    print(f"  {'已更新' if stale else '无变化'} data/entry/: {len(shards)} 个分片，"
          f"{total_bytes:,} B 原始（{'、'.join(parts) if parts else '无变化'}）")
    return stale


def build_search(doc, lang='zh-cn'):
    """语言化搜索语料：slug/type/title/en/code/summary/正文摘录/别名（短键）"""
    tf = LANG_FIELDS[lang]['title']
    bf = {'zh-cn': 'body', 'en': 'body_en', 'hk': 'body_hk'}[lang]
    out = []
    for e in doc['entries']:
        body = re.sub(r'\s+', ' ', re.sub(r'\[\[[^\]]*\]\]', ' ', e.get(bf) or e.get('body') or '')).strip()
        # 摘要不进语料：搜索结果用页面已加载的 index 里的 summary（查询时按 slug 合并）
        rec = {
            's': e['slug'],
            't': e['type'],
            'n': clean_title(e.get(tf) or e.get('title') or '', 60),
            'e': clean_title(e.get('en') or e.get('title_en') or '', 60),
        }
        # 跨语言标题：保证「EN 界面搜中文」「中文界面搜英文」仍能命中（正文级跨语言不再保留）
        if lang == 'en':
            cross = e.get('title') or ''
        else:
            cross = e.get('title_en') or e.get('en') or ''
        if cross and cross != rec['n']:
            rec['x'] = clip(cross, 60)
        if e.get('code'):
            rec['c'] = e['code']
        if e.get('aliases'):
            rec['a'] = e['aliases'][:6]
        if body:
            rec['b'] = clip(body, BODY_EXCERPT)
        out.append(rec)
    return {'generated_from': 'entries.json', 'lang': lang, 'entries': out}


def build_sitemap(doc):
    """生成 sitemap.xml：静态页 + 全部词条 + 全部周报"""
    lastmod = datetime.date.fromtimestamp(os.path.getmtime(ENTRIES)).isoformat()
    urls = []
    for p in STATIC_PATHS:
        urls.append((SITE + p, lastmod))
    for e in doc['entries']:
        urls.append((SITE + '/wiki.html?slug=' + e['slug'], None))
    wk_path = os.path.join(ROOT, 'data', 'weekly.json')
    if os.path.exists(wk_path):
        with open(wk_path, encoding='utf-8') as f:
            for r in json.load(f).get('reports', []):
                urls.append((SITE + '/weekly.html?week=' + r['slug'], None))
    out = ['<?xml version="1.0" encoding="UTF-8"?>',
           '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for loc, mod in urls:
        out.append('  <url><loc>' + loc.replace('&', '&amp;') + '</loc>' +
                   (('<lastmod>' + mod + '</lastmod>') if mod else '') + '</url>')
    out.append('</urlset>')
    return '\n'.join(out) + '\n'


def write_raw_or_check(path, text, check):
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
    print(f"  {'已更新' if changed else '无变化'} {os.path.relpath(path, ROOT)}: {len(data):,} B")
    return changed


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
    for lang, (ipath, gpath) in LANG_OUT.items():
        stale |= write_or_check(os.path.join(ROOT, ipath), build_index(doc, lang), check)
        stale |= write_or_check(os.path.join(ROOT, gpath), build_graph(doc, lang), check)
    for lang, spath in SEARCH_OUT.items():
        stale |= write_or_check(os.path.join(ROOT, spath), build_search(doc, lang), check)
    for lang, tpath in TITLES_OUT.items():
        stale |= write_or_check(os.path.join(ROOT, tpath), build_titles(doc, lang), check)
    stale |= write_shards_or_check(build_entry_shards(doc), check)
    stale |= write_raw_or_check(SITEMAP, build_sitemap(doc), check)
    if check and stale:
        print("✗ 生成物与 entries.json 不同步 —— 请运行 python3 scripts/build.py 并提交")
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
