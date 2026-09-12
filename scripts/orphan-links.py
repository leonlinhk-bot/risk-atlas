#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""#10 孤儿词条治理（方案 A：精准补链，先出候选清单）

做两件事：
1. 用 data/graph.json（正文双链 + usedIn 边）计算**真实零入链**词条（孤儿）。
2. 对每个孤儿，扫描其他词条正文里「出现其完整标题但未加 [[ ]]」的位置作为候选补链点。
   规则（保守，宁缺毋滥）：
   - 标题长度门槛：中文 ≥4 字 / 拉丁 ≥6 字符；跳过过于泛化的标题（见 STOPWORDS）
   - 只在**同语言正文**中匹配（中文标题→body；英文名→body_en；繁体标题→body_hk）
   - 命中位置若已处于 [[...]] 之内则跳过
   - 每个孤儿最多保留 N 条候选；每个目标词条最多被补 M 条（防止单页被灌满）
   - 默认 --dry-run：只输出报告到 ima-materials/orphan-links-report.md，不改数据

用法：
  python3 scripts/orphan-links.py                 # 生成候选报告（dry-run，默认）
  python3 scripts/orphan-links.py --max-per-orphan 5 --max-per-target 3
  python3 scripts/orphan-links.py --apply         # 按候选写入 entries.json（谨慎：会改正文）
"""
import json
import os
import re
import sys
from collections import Counter, defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENTRIES = os.path.join(ROOT, 'data', 'entries.json')
GRAPH = os.path.join(ROOT, 'data', 'graph.json')
REPORT = os.path.join(os.path.dirname(ROOT), 'ima-materials', 'orphan-links-report.md')

STOPWORDS = {
    'AI', 'PDF', 'Excel', 'Word', 'GPT', 'API', 'LLM', 'SQL', 'R', 'Python',
    '课程', '概念', '工具', '框架', '考牌', '岗位', '雇主', '渠道', '资源', '纵深线',
    'Overview', 'Notes', 'Tool', 'Tools', 'Model',
}
LINK_SPAN = re.compile(r'\[\[[^\]]*\]\]')


def latin_len(s):
    return len(re.findall(r'[A-Za-z0-9]', s))


def usable_title(t):
    t = (t or '').strip()
    if not t or t in STOPWORDS:
        return False
    han = len(re.findall(r'[\u4e00-\u9fff]', t))
    if han >= 4:
        return True
    return latin_len(t) >= 6 and len(t) >= 6


def masked(text):
    """把 [[...]] 区间替换为等长占位，避免在链接内部再次匹配"""
    return LINK_SPAN.sub(lambda m: '\x00' * len(m.group(0)), text)


def naive_links(entries):
    d = defaultdict(set)
    have = {e['slug'] for e in entries}
    for e in entries:
        for f in ('body', 'body_en', 'body_hk'):
            for m in LINK_SPAN.finditer(e.get(f) or ''):
                tgt = m.group(0)[2:-2].split('|')[0].strip()
                if tgt in have and tgt != e['slug']:
                    d[tgt].add(e['slug'])
    return d


SIB_REPORT = os.path.join(os.path.dirname(ROOT), 'ima-materials', 'orphan-siblings-report.md')


def siblings(entries, idx, indeg, apply_mode):
    """同类互链（方案 B2）：按 category 环形互链 + 中心枢纽链接。

    规则：
    - 只处理 tool 类孤儿（零入链）
    - 同一 category 内：按入度降序排列；每个成员链接「环上后 3 位」+「本类入度最高的 1-2 个枢纽」
    - 成员数 <4 的分类跳过（无法形成无自链的环）
    - 每个条目最多追加 5 条链接；已在正文出现过的链接不重复加
    """
    from collections import defaultdict
    cats = defaultdict(list)
    for e in entries:
        if e['type'] == 'tool' and indeg[e['slug']] == 0:
            cats[e.get('category') or '其他'].append(e)

    lines = ['# 孤儿工具「同类互链」候选报告（方案 B2 · dry-run）\n',
             f'> 脚本：`scripts/orphan-links.py --siblings`｜孤儿工具 {sum(len(v) for v in cats.values())} 条，覆盖 {len(cats)} 个分类\n',
             '## 概览\n']
    plan = []
    skipped = []
    for cat, members in sorted(cats.items(), key=lambda kv: -len(kv[1])):
        if len(members) < 4:
            skipped.append((cat, len(members)))
            continue
        ordered = sorted(members, key=lambda e: (-indeg[e['slug']], e['slug']))
        hubs = ordered[:2]
        for i, e in enumerate(ordered):
            targets = []
            for k in (1, 2, 3):
                t = ordered[(i + k) % len(ordered)]
                if t['slug'] != e['slug'] and t['slug'] not in targets:
                    targets.append(t['slug'])
            for h in hubs:
                if h['slug'] != e['slug'] and h['slug'] not in targets:
                    targets.append(h['slug'])
            plan.append((cat, e['slug'], targets[:5]))

    would_receive = set()
    for _cat, _src, targets in plan:
        for t in targets:
            would_receive.add(t)
    all_orphan_tools = {e['slug'] for v in cats.values() for e in v}
    covered = len(all_orphan_tools & would_receive)

    lines.append(f'- 将追加同类互链的条目：**{len(plan)}** 条（每条约 3–5 个链接）')
    lines.append(f'- 预计获得入链的孤儿工具：**{covered} / {len(all_orphan_tools)}**')
    lines.append(f'- 跳过（分类成员 <4）：{len(skipped)} 个分类 → {skipped[:6]}')
    lines.append('\n## 样本（前 12 条）\n')
    lines.append('| 孤儿工具 | 分类 | 拟链接到（slug） |')
    lines.append('|---|---|---|')
    for cat, src, targets in plan[:12]:
        lines.append(f'| `{src}` | {cat} | ' + '、'.join('`' + t + '`' for t in targets) + ' |')
    lines.append('\n## 说明\n')
    lines.append('- 「环形互链」保证同类孤儿彼此获得入链（每条被环上 3 个同伴指向）；「中心枢纽」链接提升导航质量。')
    lines.append('- 追加形式为独立段落：`## 同类工具\n[[a]]、[[b]]、[[c]]`（三语同步；不修改原有正文）。')
    lines.append('- 默认仅出报告；确认后运行 `--siblings --apply` 写入。')
    with open(SIB_REPORT, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines) + '\n')
    print(f'✓ 报告已写入 {os.path.relpath(SIB_REPORT, os.path.dirname(ROOT))}')
    print(f'  拟追加 {len(plan)} 条 | 预计获得入链 {covered}/{len(all_orphan_tools)} | 跳过分类 {len(skipped)}')

    if apply_mode:
        LAB = {'zh': '## 同类工具', 'en': '## Similar tools', 'hk': '## 同類工具'}
        added = 0
        for cat, src, targets in plan:
            e = idx[src]
            block_zh = LAB['zh'] + '\n' + '、'.join('[[' + t + ']]' for t in targets)
            block_en = LAB['en'] + '\n' + '、'.join('[[' + t + ']]' for t in targets)
            block_hk = LAB['hk'] + '\n' + '、'.join('[[' + t + ']]' for t in targets)
            for field, block in (('body', block_zh), ('body_en', block_en), ('body_hk', block_hk)):
                cur = e.get(field) or ''
                if LAB['zh'] in cur or LAB['en'] in cur or LAB['hk'] in cur:
                    continue
                e[field] = (cur.rstrip() + '\n\n' + block) if cur.strip() else block
            added += 1
        doc2 = json.load(open(ENTRIES, encoding='utf-8'))
        doc2['entries'] = entries
        json.dump(doc2, open(ENTRIES, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
        with open(ENTRIES, 'a', encoding='utf-8') as f:
            f.write('\n')
        print(f'✓ 已为 {added} 条条目追加「同类工具」段落（请跑 validate-entries.py + build.py 后提交）')
    return 0


def main():
    args = sys.argv[1:]
    apply_mode = '--apply' in args
    siblings_mode = '--siblings' in args
    max_per_orphan = 5
    max_per_target = 3
    for i, a in enumerate(args):
        if a == '--max-per-orphan' and i + 1 < len(args):
            max_per_orphan = int(args[i + 1])
        if a == '--max-per-target' and i + 1 < len(args):
            max_per_target = int(args[i + 1])

    doc = json.load(open(ENTRIES, encoding='utf-8'))
    entries = doc['entries']
    idx = {e['slug']: e for e in entries}

    # 入度：直接数「其它词条正文（三语）里指向本词的 [[slug]]」——与词条页「反向链接」口径一致。
    # 注意：不能用 graph.json 的 target 计数，因为该文件为去重会把互链方向合并（会误判孤儿）。
    graph = json.load(open(GRAPH, encoding='utf-8'))
    indeg = Counter()
    for tgt, srcs in naive_links(entries).items():
        indeg[tgt] = len(srcs)
    orphans = [e for e in entries if indeg[e['slug']] == 0]
    by_type = Counter(e['type'] for e in orphans)

    # 候选：在其他词条正文里找「完整标题但未加链接」
    cand = defaultdict(list)          # orphan slug -> [(target slug, field, count)]
    target_load = Counter()
    for e in orphans:
        fields = [('body', e.get('title')), ('body_en', e.get('title_en') or e.get('en')), ('body_hk', e.get('title_hk'))]
        fields = [(f, t) for f, t in fields if usable_title(t)]
        if not fields:
            continue
        for other in entries:
            if other['slug'] == e['slug']:
                continue
            if target_load[other['slug']] >= max_per_target:
                continue
            for field, title in fields:
                text = other.get(field) or ''
                if not text:
                    continue
                if title in LINK_SPAN.findall(text):
                    continue
                hits = masked(text).count(title)
                if hits:
                    cand[e['slug']].append((other['slug'], field, hits))
                    target_load[other['slug']] += 1
                    break
        cand[e['slug']] = cand[e['slug']][:max_per_orphan]

    have_cand = [s for s in cand if cand[s]]
    total_links = sum(len(v) for v in cand.values())
    still_stranded = len(orphans) - len(have_cand)

    lines = []
    lines.append('# 孤儿词条补链候选报告（方案 A · dry-run）\n')
    lines.append(f'> 生成脚本：`scripts/orphan-links.py`｜数据：{len(entries)} 词条，graph 边 {len(graph["links"])} 条\n')
    lines.append('## 概览\n')
    lines.append(f'- 零入链（含 usedIn 边）词条：**{len(orphans)}** 条 → 类型分布：{dict(by_type)}')
    lines.append(f'- 找到候选补链点的孤儿：**{len(have_cand)}** 条，预计新增双链 **{total_links}** 条')
    lines.append(f'- 仍无候选（正文里从未被提及）：**{still_stranded}** 条')
    lines.append(f'- 上限：每孤儿 ≤{max_per_orphan} 条、每目标词条 ≤{max_per_target} 条\n')
    lines.append('## 候选明细（最多展示 60 行）\n')
    lines.append('| 孤儿（slug / 标题） | 可补链到 | 位置 | 命中次数 |')
    lines.append('|---|---|---|---|')
    shown = 0
    for slug, lst in sorted(cand.items(), key=lambda kv: -len(kv[1])):
        if not lst:
            continue
        title = idx[slug].get('title', '')
        first = True
        for tgt, field, hits in lst:
            if shown >= 60:
                break
            label = f'`{slug}`<br>{title[:26]}' if first else ''
            lines.append(f'| {label} | `{tgt}` | {field} | {hits} |')
            first = False
            shown += 1
    lines.append('')
    lines.append('## 说明\n')
    lines.append('- 匹配规则：**完整标题**精确匹配、同语言正文、且不在已有 `[[ ]]` 内；命中即建议插入 `[[slug|原文字样]]`（保留原文）。')
    lines.append('- 仅生成报告，未修改任何数据；确认后再跑 `--apply`。')
    lines.append('- 未被任何正文提及的孤儿，建议走方案 B（课程页/纵深线页加「相关工具」入口）。')

    report = '\n'.join(lines) + '\n'
    with open(REPORT, 'w', encoding='utf-8') as f:
        f.write(report)
    print(f'✓ 报告已写入 {os.path.relpath(REPORT, os.path.dirname(ROOT))}')
    print(f'  零入链 {len(orphans)} → 有候选 {len(have_cand)}（新增链接 {total_links}）→ 仍孤立 {still_stranded}')
    print('  类型分布：', dict(by_type))

    if siblings_mode:
        return siblings(entries, idx, indeg, apply_mode)
    if apply_mode:
        added = 0
        for slug, lst in cand.items():
            for tgt, field, _hits in lst:
                other = idx[tgt]
                title = idx[slug].get('title') if field == 'body' else (idx[slug].get('title_en') or idx[slug].get('en')) if field == 'body_en' else idx[slug].get('title_hk')
                if not title:
                    continue
                text = other.get(field) or ''
                pos = masked(text).find(title)
                if pos < 0:
                    continue
                other[field] = text[:pos] + f'[[{slug}|{title}]]' + text[pos + len(title):]
                added += 1
        json.dump(doc, open(ENTRIES, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
        with open(ENTRIES, 'a', encoding='utf-8') as f:
            f.write('\n')
        print(f'✓ 已写入 {added} 条补链（请跑 validate-entries.py + build.py 后提交）')
    return 0


if __name__ == '__main__':
    sys.exit(main())
