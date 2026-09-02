#!/usr/bin/env python3
"""Risk Atlas entries.json 上线前校验器。

用法: python3 scripts/validate-entries.py
PASS(exit 0) 才允许 push。硬错(hard) = JSON 损坏/缺必填/重复 slug/类型非法 → FAIL；
软错(soft) = 悬空 [[双链]]、en/hk 字段缺失 → 仅警告。
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ENTRIES = ROOT / "data" / "entries.json"
ALLOWED_TYPES = {
    "course", "concept", "tool", "framework", "track",
    "credential", "job", "employer", "channel", "resource", "website",
}
REQUIRED = ["slug", "type", "title", "summary", "body"]

errors, warnings = [], []

try:
    data = json.loads(ENTRIES.read_text(encoding="utf-8"))
except Exception as e:
    print(f"FAIL: entries.json 无法解析: {e}")
    sys.exit(1)

if not isinstance(data, dict) or "site" not in data or "entries" not in data:
    errors.append('顶层结构应为 {"site": {...}, "entries": [...]}')
    print("\n".join(errors))
    sys.exit(1)

entries = data["entries"]
if not isinstance(entries, list) or not entries:
    errors.append("entries 为空")
    print("FAIL: entries 为空")
    sys.exit(1)

slugs = {}
for i, e in enumerate(entries):
    if not isinstance(e, dict):
        continue
    s = e.get("slug")
    if s:
        if s in slugs:
            errors.append(f"slug 重复: {s}（entries[{slugs[s]}] 与 entries[{i}]）")
        slugs[s] = i

for i, e in enumerate(entries):
    if not isinstance(e, dict):
        errors.append(f"entries[{i}] 不是对象")
        continue
    for field in REQUIRED:
        if not e.get(field) or not str(e[field]).strip():
            errors.append(f"entries[{i}] slug={e.get('slug','?')} 缺必填字段: {field}")
    t = e.get("type")
    if t not in ALLOWED_TYPES:
        errors.append(f"entries[{i}] slug={e.get('slug','?')} type 非法: {t}（允许: {sorted(ALLOWED_TYPES)}）")
    # 悬空双链（软）——须在完整 slug 表建成后扫描
    body = e.get("body") or ""
    for m in re.findall(r"\[\[([^\]]+)\]\]", body):
        if m not in slugs:
            warnings.append(f"悬空双链: {e.get('slug','?')} -> [[{m}]]")

# en/hk 缺失（软，仅提示）
missing_i18n = sum(1 for e in entries if not (e.get("title_en") and e.get("body_en") and e.get("summary_en")))
missing_hk = sum(1 for e in entries if not (e.get("title_hk") and e.get("body_hk") and e.get("summary_hk")))

if errors:
    print(f"FAIL: {len(errors)} 个硬错误（禁止推送）")
    for e in errors[:20]:
        print("  ✗", e)
    if len(errors) > 20:
        print(f"  … 还有 {len(errors)-20} 个")
    sys.exit(1)

print(f"✅ PASS: {len(entries)} 词条（{len(slugs)} 唯一 slug）")
if warnings:
    print(f"   ⚠ {len(warnings)} 条悬空双链（建议修，不阻塞）")
    for w in warnings[:10]:
        print("     ", w)
if missing_i18n:
    print(f"   ⚠ {missing_i18n} 词条缺 en 字段 / {missing_hk} 词条缺 hk 字段（建议补）")
sys.exit(0)
