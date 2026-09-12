#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""#12 薄条目模板化：为正文 <80 字符的词条补「结构化」正文。

原则：
- **只用词条已有字段**（summary / category / site / source / courses / concepts / status），
  不新增任何未经核实的事实。
- 课程类若正文是「非官方 Indicative Content…待核实」这类**有意的免责声明**，一律跳过。
- 三语同步：正文按 body / body_en / body_hk 分别用对应语言的 summary 生成。
- 幂等：只在正文 <80 字符时补写；补写后自然超过阈值，重复运行不再改动。

用法：
  python3 scripts/enrich-thin.py --dry-run   # 预览（打印统计与样本，不写入）
  python3 scripts/enrich-thin.py             # 写回 data/entries.json
"""
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENTRIES = os.path.join(ROOT, 'data', 'entries.json')
THIN = 80
SKIP_MARKERS = ('非官方 Indicative Content', '待官方', '正式笔记待取得')

LABELS = {
    'zh': {
        'overview': '简介', 'facts': '机构信息', 'info': '基本信息', 'type': '机构类型', 'site': '官网',
        'usage': '用途', 'entry': '入口', 'what': '是什么', 'category': '类别',
        'source': '来源', 'related': '相关', 'status': '状态',
        'employer_note': '招聘与业务信息以机构官方渠道为准。',
        'tool_note': '尚未在本站实测：来源与可用性待验证。',
    },
    'hk': {
        'overview': '簡介', 'facts': '機構資訊', 'info': '基本資訊', 'type': '機構類型', 'site': '官網',
        'usage': '用途', 'entry': '入口', 'what': '是什麼', 'category': '類別',
        'source': '來源', 'related': '相關', 'status': '狀態',
        'employer_note': '招聘與業務資訊以機構官方渠道為準。',
        'tool_note': '尚未在本站實測：來源與可用性待驗證。',
    },
    'en': {
        'overview': 'Overview', 'facts': 'Facts', 'info': 'Key facts', 'type': 'Type', 'site': 'Website',
        'usage': 'Purpose', 'entry': 'Entry', 'what': 'What it is', 'category': 'Category',
        'source': 'Source', 'related': 'Related', 'status': 'Status',
        'employer_note': 'Hiring and business details follow the institution’s official channels.',
        'tool_note': 'Not yet tested on this site — source and availability pending verification.',
    },
}


def tx(e, field, lang):
    if lang == 'en':
        return (e.get(field + '_en') or e.get(field) or '').strip()
    if lang == 'hk':
        return (e.get(field + '_hk') or e.get(field) or '').strip()
    return (e.get(field) or '').strip()


def domain(e):
    s = (e.get('site') or e.get('source') or '').strip()
    return re.sub(r'^https?://', '', s).rstrip('/')


def build_body(e, lang):
    t = e['type']
    L = LABELS[lang]
    SEP = ': ' if lang == 'en' else '：'
    summary = tx(e, 'summary', lang)
    parts = []
    # 保留原有正文（可能含 [[双链]] 与具体事实），模板只在其上补结构
    keep = (e.get('body') if lang == 'zh' else e.get('body_' + ('en' if lang == 'en' else 'hk'))) or e.get('body') or ''
    keep = keep.strip()

    if t == 'employer':
        parts.append('## ' + L['overview'] + '\n' + (keep or summary))
        facts = []
        if e.get('category'):
            facts.append('- ' + L['type'] + SEP + str(e['category']))
        d = domain(e)
        if d:
            facts.append('- ' + L['site'] + SEP + d)
        if facts:
            parts.append('## ' + L['facts'] + '\n' + '\n'.join(facts))
        parts.append('> ' + L['employer_note'])

    elif t == 'channel':
        parts.append('## ' + L['usage'] + '\n' + (keep or summary))
        facts = []
        if e.get('category'):
            facts.append('- ' + L['type'] + SEP + str(e['category']))
        d = domain(e)
        if d:
            facts.append('- ' + L['entry'] + SEP + d)
        if facts:
            parts.append('## ' + L['facts'] + '\n' + '\n'.join(facts))

    elif t == 'tool':
        parts.append('## ' + L['what'] + '\n' + (keep or summary))
        facts = ['- ' + L['category'] + SEP + str(e.get('category') or '—')]
        d = domain(e)
        if d:
            facts.append('- ' + L['source'] + SEP + d)
        parts.append('## ' + L['info'] + '\n' + '\n'.join(facts))
        parts.append('> ' + L['tool_note'])

    else:  # concept / framework / credential / 其他
        parts.append(keep or summary)
        rel = []
        for c in (e.get('courses') or [])[:5]:
            rel.append('[[' + c + ']]')
        for c in (e.get('concepts') or [])[:5]:
            rel.append('[[' + c + ']]')
        if rel:
            parts.append('## ' + L['related'] + '\n' + '、'.join(rel))
        if e.get('status'):
            parts.append('- ' + L['status'] + SEP + str(e['status']))

    return '\n\n'.join(p for p in parts if p and p.strip())


def main():
    dry = '--dry-run' in sys.argv
    doc = json.load(open(ENTRIES, encoding='utf-8'))
    changed = []
    for e in doc['entries']:
        body = e.get('body') or ''
        if len(body) >= THIN:
            continue
        if any(m in body for m in SKIP_MARKERS):
            continue
        # 非雇主/渠道/工具类：原文若已含双链与实质内容，说明是为「卡片式一句话」，不强行套模板
        if e['type'] not in ('employer', 'channel', 'tool') and '[[' in body:
            continue
        new_zh = build_body(e, 'zh')
        new_en = build_body(e, 'en')
        new_hk = build_body(e, 'hk')
        if len(new_zh) <= len(body):
            continue
        changed.append((e, new_zh, new_en, new_hk))

    print(f'待补写：{len(changed)} 条（正文 <{THIN} 字符，且非免责声明类）')
    from collections import Counter
    print('  类型分布：', dict(Counter(e['type'] for e, *_ in changed)))
    for e, zh, en, hk in changed[:3]:
        print('\n--- 样本:', e['slug'], '|', e['title'][:36])
        print('[原文]', repr((e.get('body') or '')[:60]))
        print('[新文]\n' + zh)

    if dry:
        print('\n（--dry-run：未写入）')
        return 0

    for e, zh, en, hk in changed:
        e['body'] = zh
        e['body_en'] = en
        e['body_hk'] = hk
    json.dump(doc, open(ENTRIES, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
    with open(ENTRIES, 'a', encoding='utf-8') as f:
        f.write('\n')
    print(f'✓ 已补写 {len(changed)} 条三语正文')
    return 0


if __name__ == '__main__':
    sys.exit(main())
