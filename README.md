# Risk Atlas · 风险图谱

岭南大学 MSc in Risk, Insurance and Actuarial Analytics (MScRIAA，原 MScRIM) 的开放知识百科。

- **90 词条**：课程 / 概念 / 工具 / 框架 / 纵深线 / 考牌
- **三语**：English（优先）/ 简体中文 / 繁體中文
- **双链**：正文 `[[slug]]` 互链 + 自动反向链接 + 知识图谱
- **纯静态**：无后端，加词条 = 在 `data/entries.json` 加一个对象

## 本地预览

```bash
python3 -m http.server 8000
# 打开 http://127.0.0.1:8000/
```

> 不要直接双击 index.html（file:// 下 fetch 会被拦截），需走静态服务器。

## 部署

本仓库已配置 GitHub Actions（`.github/workflows/deploy-pages.yml`），push 到 `main` 分支即自动部署到 GitHub Pages。需在仓库 Settings → Pages 将 Source 设为 **GitHub Actions**。
