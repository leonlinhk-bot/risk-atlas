#!/usr/bin/env bash
# verify-live.sh — push 后自动核验线上与本地一致（替代人工 sleep + shasum 手动比对）
#
# 用法：
#   scripts/verify-live.sh                 # 默认：等待最多 180s，核验常用文件 + 页面状态 + 数据计数
#   scripts/verify-live.sh --wait 300      # 自定义最长等待（秒）
#   scripts/verify-live.sh --interval 10   # 自定义轮询间隔（秒）
#   scripts/verify-live.sh index.html css/style.css   # 只核验指定文件
#   scripts/verify-live.sh --wait 0        # 不等待，只跑一遍
#
# 退出码：0 = 全部一致；1 = 超时仍有文件不一致或页面状态异常
set -uo pipefail

SITE="${SITE:-https://risk-atlas.wiki}"
WAIT=180
INTERVAL=15
FILES=()

while [ $# -gt 0 ]; do
  case "$1" in
    --wait)     WAIT="$2"; shift 2 ;;
    --interval) INTERVAL="$2"; shift 2 ;;
    -h|--help)  sed -n '2,12p' "$0"; exit 0 ;;
    *)          FILES+=("$1"); shift ;;
  esac
done

if [ ${#FILES[@]} -eq 0 ]; then
  FILES=(
    index.html career.html weekly.html map.html categories.html catalog.html companies.html wiki.html 404.html
    robots.txt sitemap.xml
    css/style.css js/wiki.js js/nav.js js/search.js js/graph.js js/notice.js js/vendor/echarts.min.js
    data/index.json data/index.en.json data/index.hk.json data/graph.json data/graph.en.json
    data/search.json data/search.en.json data/search.hk.json
    data/entries.json data/weekly.json data/job-postings.json data/career-trends.json data/companies.json
  )
fi

echo "→ 目标站点：${SITE}（最长等待 ${WAIT}s，间隔 ${INTERVAL}s）"

# 过滤本地不存在的文件（例如尚未自托管的资源）
PENDING=()
for f in "${FILES[@]}"; do
  if [ -f "$f" ]; then PENDING+=("$f"); else echo "  skip ${f}（本地不存在）"; fi
done

START=$(date +%s)
DEADLINE=$((START + WAIT))
ATTEMPT=0
FAILED=()

while :; do
  ATTEMPT=$((ATTEMPT + 1))
  STILL=()
  MISMATCH=0
  for f in "${PENDING[@]}"; do
    local_sum=$(shasum -a 256 "$f" | awk '{print $1}')
    # 必须 --compressed：Cloudflare 对 robots.txt / data/entries.json 等会无条件回 gzip，
    # 不加该参数拿到的是压缩字节，哈希必然不一致（假阴性）。
    remote_sum=$(curl -s --compressed --max-time 60 "$SITE/$f?cb=$(date +%s%N)" | shasum -a 256 | awk '{print $1}')
    if [ "$local_sum" = "$remote_sum" ]; then
      [ "$ATTEMPT" -eq 1 ] && echo "  OK   $f"
    else
      MISMATCH=$((MISMATCH + 1)); STILL+=("$f")
    fi
  done

  if [ ${#STILL[@]} -eq 0 ]; then
    echo "✓ 文件一致性核验通过（${ATTEMPT} 次轮询，用时 $(( $(date +%s) - START ))s）：${#PENDING[@]} 个文件"
    break
  fi
  NOW=$(date +%s)
  if [ "$NOW" -ge "$DEADLINE" ]; then
    echo "✗ 等待超时：以下 ${#STILL[@]} 个文件仍与本地不一致："
    printf '    - %s\n' "${STILL[@]}"
    FAILED=("${STILL[@]}")
    break
  fi
  echo "  … 第 $ATTEMPT 次：${#STILL[@]} 个文件尚未同步，${INTERVAL}s 后重试"
  sleep "$INTERVAL"
done

echo "→ 页面状态："
PAGES=(index.html career.html weekly.html map.html categories.html catalog.html companies.html wiki.html robots.txt sitemap.xml)
PAGE_FAIL=0
for p in "${PAGES[@]}"; do
  code=$(curl -s -o /dev/null -w '%{http_code}' --max-time 25 "$SITE/$p")
  if [ "$code" = "200" ]; then printf '  OK   %-16s 200\n' "$p"; else printf '  FAIL %-16s %s\n' "$p" "$code"; PAGE_FAIL=1; fi
done
code404=$(curl -s -o /dev/null -w '%{http_code}' --max-time 25 "$SITE/no-such-page-verify")
if [ "$code404" = "404" ]; then echo "  OK   404 页          404（品牌化）"; else echo "  FAIL 404 页          $code404"; PAGE_FAIL=1; fi

echo "→ 数据计数："

# 带重试的远程取数（大文件 + 连续请求易被限速，故压缩传输 + 3 次退避重试）
fetch_retry() {  # $1=url  $2=处理命令（读 stdin）
  local url="$1" proc="$2" out='' i=1
  while [ "$i" -le 3 ]; do
    out=$(curl -s --compressed --max-time 60 "$url" 2>/dev/null | eval "$proc" 2>/dev/null)
    [ -n "$out" ] && { echo "$out"; return 0; }
    sleep 5; i=$((i + 1))
  done
  echo '?'; return 1
}

LOCAL_ENTRIES=$(python3 -c "import json;print(len(json.load(open('data/entries.json'))['entries']))" 2>/dev/null || echo '?')
REMOTE_ENTRIES=$(fetch_retry "$SITE/data/entries.json" "python3 -c \"import sys,json;print(len(json.load(sys.stdin)['entries']))\"")
[ "$LOCAL_ENTRIES" = "$REMOTE_ENTRIES" ] && echo "  OK   词条数 ${REMOTE_ENTRIES}" || { echo "  FAIL 词条数 本地 ${LOCAL_ENTRIES} / 线上 ${REMOTE_ENTRIES}"; PAGE_FAIL=1; }

LOCAL_SM=$(grep -c '<loc>' sitemap.xml 2>/dev/null || echo '?')
REMOTE_SM=$(fetch_retry "$SITE/sitemap.xml" "grep -c '<loc>'")
[ "$LOCAL_SM" = "$REMOTE_SM" ] && echo "  OK   sitemap URL ${REMOTE_SM}" || { echo "  FAIL sitemap 本地 ${LOCAL_SM} / 线上 ${REMOTE_SM}"; PAGE_FAIL=1; }

if [ ${#FAILED[@]} -gt 0 ] || [ "$PAGE_FAIL" -ne 0 ]; then
  echo "✗ 核验未通过"; exit 1
fi
echo "✓ 线上核验全部通过"
