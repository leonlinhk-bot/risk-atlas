#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""给 HTML 里的 css/js 引用加内容指纹（?v=<sha256 前 8 位>），实现长缓存 + 更新即失效。

用法：
  python3 scripts/stamp.py          # 就地更新所有 *.html
  python3 scripts/stamp.py --check  # 只检查是否已是最新指纹（CI 用，过期 exit 1）

说明：
- 只处理 HTML 中 <link href="css/..."> 与 <script src="js/..."> 两类引用（含已有的 ?v=）。
- 数据文件（data/*.json）不加指纹：它们由 JS 运行时 fetch，缓存策略交给 Cloudflare 规则
  （见 ima-materials/hermes-cache-rule.md：/data/* 短 TTL，/css/* 与 /js/* 长 TTL）。
- 幂等：重复运行结果一致。
"""
import glob
import hashlib
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PAGES = sorted(glob.glob(os.path.join(ROOT, '*.html')))
# 同时给 404.html 盖章（若存在）
RE_CSS = re.compile(r'(href=")(css/[^"?]+\.css)(\?v=[0-9a-f]+)?(")')
RE_JS = re.compile(r'(src=")(js/[^"?]+\.js)(\?v=[0-9a-f]+)?(")')


def digest(rel):
    path = os.path.join(ROOT, rel)
    if not os.path.exists(path):
        raise FileNotFoundError(rel)
    with open(path, 'rb') as f:
        return hashlib.sha256(f.read()).hexdigest()[:8]


def stamp_text(text):
    changed = {'css': 0, 'js': 0}

    def repl_css(m):
        v = digest(m.group(2))
        if m.group(3) != '?v=' + v:
            changed['css'] += 1
        return m.group(1) + m.group(2) + '?v=' + v + m.group(4)

    def repl_js(m):
        v = digest(m.group(2))
        if m.group(3) != '?v=' + v:
            changed['js'] += 1
        return m.group(1) + m.group(2) + '?v=' + v + m.group(4)

    text = RE_CSS.sub(repl_css, text)
    text = RE_JS.sub(repl_js, text)
    return text, changed


def main():
    check = '--check' in sys.argv
    stale = []
    for page in PAGES:
        with open(page, encoding='utf-8') as f:
            text = f.read()
        new, changed = stamp_text(text)
        rel = os.path.relpath(page, ROOT)
        if new != text:
            stale.append(rel)
            if not check:
                with open(page, 'w', encoding='utf-8') as f:
                    f.write(new)
    if check:
        if stale:
            print('✗ 指纹过期（请运行 python3 scripts/stamp.py 并提交）: ' + ', '.join(stale))
            return 1
        print('✓ 所有 HTML 的 css/js 指纹均为最新')
        return 0
    print(('已更新: ' + ', '.join(stale)) if stale else '无需更新（指纹均为最新）')
    return 0


if __name__ == '__main__':
    sys.exit(main())
