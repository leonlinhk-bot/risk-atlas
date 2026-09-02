# Risk Atlas · 发布协议（所有编辑 agent 必读）

**线上地址：https://risk-atlas.wiki**（GitHub Pages 分支直连 + Cloudflare，无 CI，无构建）

本目录是 GitHub 仓库 `leonlinhk-bot/risk-atlas` 的工作副本，**`main` 分支 = 线上**。
`git push origin main` 后约 1 分钟自动上线。因为没有任何 CI 闸门，**上线前必须本地校验**。

---

## 常规更新（新增 / 修改词条）

```bash
# 1. 先同步远端（多人/多 agent 协作，必须先拉）
git pull origin main --rebase

# 2. 编辑 data/entries.json（schema 见下）

# 3. 校验（必须 PASS 才能推）
python3 scripts/validate-entries.py

# 4. 提交并推送 → 自动上线
git add data/entries.json
git commit -m "词条: <改动摘要，如 新增 AI 工具 xx / 补全 RIM537 概念>"
git push origin main
```

推送成功后可用以下命令抽查线上是否已更新：

```bash
curl -s https://risk-atlas.wiki/data/entries.json | python3 -c "import sys,json;print(len(json.load(sys.stdin)['entries']),'词条已上线')"
```

## entries.json schema

```
{
  "site":    { 站点元信息，勿动 },
  "entries": [
    {
      "slug":      "唯一标识，小写连字符，如 value-at-risk",        # 必填，全局唯一
      "type":      "course|concept|tool|framework|track|credential|job|employer|channel|resource|website",  # 必填
      "title":     "简体中文标题",                                   # 必填
      "title_en":  "English title",                                 # 建议
      "title_hk":  "繁體中文標題",                                   # 建议
      "summary":   "一句话简介（首页/列表展示）",                     # 必填
      "summary_en": "...", "summary_hk": "...",                      # 建议
      "body":      "正文，双链用 [[slug]]",                           # 必填
      "body_en": "...", "body_hk": "...",                            # 建议
      "courses":   ["rim520"],     # 仅 course/track 类词条使用
      "number":    "①"             # 仅 track 类使用
    }
  ]
}
```

- 语言惯例：简体中文为主，`*_en` / `*_hk` 字段同步维护；新增词条暂时缺 en/hk 可用简中暂代，但别留空。
- 正文双链 `[[slug]]` 尽量指向**已存在**的词条（校验脚本会对悬空链接发警告）。
- 词条类型与首页统计一致：`course 课程 / concept 概念 / tool 工具(AI 工具箱) / framework 框架 / track 纵深线 / credential 考牌 / job 岗位 / employer 雇主 / channel 渠道 / resource 资源`。

## 禁区（违反会弄坏线上或仓库）

| 禁止 | 原因 |
|---|---|
| 改 `CNAME` | GitHub 自动管理自定义域名，改错即断站 |
| 改 `.nojekyll`、新增 `.github/` | 部署结构，由 Hermes 负责 |
| 提交 `data/*.bak*`、`*.zip`、大附件 | 仓库体积污染 |
| 跳过 `validate-entries.py` 直接 push | 无 CI，坏 JSON 会直接打挂线上 |
| 改动 git 历史 / 强推（`push -f`） | 多 agent 协作，历史必须线性 |

## 说明

- 本仓库内容与香港保险/公司业务**无关**，是岭南大学 MScRIAA（原 MScRIM）课程开放知识百科（含 AI 工具箱、就业情报、机构全景、周报）。
- 机构数据（保险公司/经纪行名单）在 `data/companies.json`，职业趋势在 `data/career-trends.json`——结构不同，改前先看文件内字段，别套用 entries schema。
