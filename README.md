# Risk Atlas · 风险图谱

岭南大学 MSc in Risk, Insurance and Actuarial Analytics（MScRIAA，原 MScRIM）的开放知识百科。

🌐 **线上地址：https://risk-atlas.wiki**（GitHub Pages + Cloudflare）

- **词条持续增长（1100+，实时数以首页页首统计为准）**：课程（RIM520–RIM540 十六门）/ 概念 / AI 工具箱（900+ 工具 + 网站） / 框架 / 纵深线 / 考牌 / 就业岗位 / 雇主机构
- **三语**：English（优先）/ 简体中文 / 繁體中文
- **双链**：正文 `[[slug]]` 互链 + 自动反向链接 + 知识图谱
- **就业情报**：职业路径、机构全景（保险公司 / 经纪行名单）、周报速览
- **纯静态**：无后端，加词条 = 在 `data/entries.json` 加一个对象

## 数据构建（派生文件）

```bash
python3 scripts/build.py     # data/index.<lang>.json（列表页索引）+ data/graph.<lang>.json（宇宙图）+ data/search.<lang>.json（搜索语料）
python3 scripts/stamp.py     # HTML 资源指纹（css/js ?v=）
```

改动 `data/entries.json` 后必须重跑这两条并与数据一起提交；`--check` 参数可用于 CI 校验是否过期。

## 本地预览

```bash
python3 -m http.server 8000
# 打开 http://127.0.0.1:8000/
```

> 不要直接双击 index.html（file:// 下 fetch 会被拦截），需走静态服务器。

## 部署

GitHub Pages 分支直连部署（`Settings → Pages → Source: Deploy from a branch → main / (root)`）。

```bash
git push origin main   # 即自动上线
```

## 更新流程（给 Harness / Hermes / 协作者）

> 完整协议见 **`CLAUDE.md`**（agent 打开仓库即读）。核心三步：

```bash
git pull origin main --rebase          # 1. 先同步
# 编辑 data/entries.json …
python3 scripts/validate-entries.py    # 2. 校验（PASS 才能推；pre-push hook 会自动拦截坏数据）
git add data/entries.json && git commit -m "词条: …" && git push origin main   # 3. 推送即上线（~1 分钟）
bash scripts/verify-live.sh       # 4. 自动核验线上与本地一致（含页面状态/404/计数）
```

## 页面一览

| 页面 | 内容 |
|------|------|
| index.html | 首页：搜索 / 统计 / 分类 / 热门词条 |
| wiki.html | 词条渲染（双链正文） |
| catalog.html / categories.html | 课程目录 / 分类索引 |
| career.html | 就业情报（职业趋势 / 岗位 / 招聘渠道） |
| companies.html | 机构全景（保险公司与经纪行） |
| weekly.html | 周报（data/reports/） |
| map.html | 知识宇宙 |
