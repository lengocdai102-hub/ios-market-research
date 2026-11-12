"""把竞品池拆成各 bot 的分片, 并生成运行脚本"""
import json, os, math

BASE = "/Users/maike/Desktop/iOS副业调研_2026-11-09"
INP = f"{BASE}/采集器/inputs"
SCR = f"{BASE}/采集器/scr_collect.py"
PY = "/Users/maike/.venvs/scrapling/bin/python"

apps = json.load(open(f"{INP}/competitor_ids.json"))

# 分层: 核心竞品(房车维护) / 相邻赛道 / 大流量参照
core = [a for a in apps if any(k in a["foundBy"].lower() for k in
        ["rv ", "rvk", "rv p", "rv a", "rv c", "rv l", "rv o", "rv s", "rv t", "rv e", "rv g",
         "motorhome", "camper", "recreational", "my general"])]
adj  = [a for a in apps if a not in core]
print(f"核心房车相关 {len(core)} | 相邻/参照 {len(adj)}")

# 4 个 bot, 按评分量均分核心集
SHARDS = 4
buckets = [[] for _ in range(SHARDS)]
for i, a in enumerate(sorted(core, key=lambda x: -(x.get("userRatingCount") or 0))):
    buckets[i % SHARDS].append(a)
for i, b in enumerate(buckets):
    json.dump(b, open(f"{INP}/shard_reviews_{i+1}.json", "w"), ensure_ascii=False, indent=2)
    print(f"  shard{i+1} 评论分片: {len(b)} 个 (评分量 {sum(x.get('userRatingCount') or 0 for x in b)})")

# 榜单分片: 按 genre 切
CHART_GENRES = {
 1: ["6014","6016","6012"],   # Business Navigation Lifestyle
 2: ["6020","6027","6008"],   # Travel Health-Fitness Finance
 3: ["6024","6018","6007"],   # Medical Education Productivity
 4: ["6005","6011","6022","6006"],  # Social Reference Developer-Tools Utilities
}
for i, gs in CHART_GENRES.items():
    json.dump(gs, open(f"{INP}/shard_charts_{i}.json","w"), ensure_ascii=False)

# 社区查询分片
QUERIES = json.load(open(f"{INP}/community_queries.json"))
qb = [[] for _ in range(SHARDS)]
for i, q in enumerate(QUERIES):
    qb[i % SHARDS].append(q)
for i, b in enumerate(qb):
    json.dump(b, open(f"{INP}/shard_community_{i+1}.json","w"), ensure_ascii=False, indent=2)
    print(f"  shard{i+1} 社区分片: {len(b)} 个查询")

# lookup 词分片
TERMS = json.load(open(f"{INP}/lookup_terms.json"))
tb = [TERMS[i::SHARDS] for i in range(SHARDS)]
for i, b in enumerate(tb):
    json.dump(b, open(f"{INP}/shard_lookup_{i+1}.json","w"), ensure_ascii=False, indent=2)

# ---- 生成 4 个 bot 的运行脚本 ----
BOT_DIR = f"{BASE}/采集器/bots"
os.makedirs(BOT_DIR, exist_ok=True)

SCRIPTS = {
 1: f'''#!/bin/bash
# Bot1: 核心房车竞品 —— 评论 + 评分分布
set -u
D="{BASE}/采集器"
O="$D/out_bot1"; mkdir -p "$O"
export SCR_OUT="$O"
cd "$D"
echo "[bot1] 核心竞品评论采集"
{PY} "$D/scr_collect.py" reviews --ids "$D/inputs/shard_reviews_1.json" --delay 1.2
{PY} "$D/scr_collect.py" charts --delay 0.6
echo "[bot1] DONE"
''',
 2: f'''#!/bin/bash
# Bot2: 相邻赛道竞品 + 榜单
set -u
D="{BASE}/采集器"
O="$D/out_bot2"; mkdir -p "$O"
export SCR_OUT="$O"
cd "$D"
echo "[bot2] 相邻竞品评论 + 竞品详情"
{PY} "$D/scr_collect.py" reviews --ids "$D/inputs/shard_reviews_2.json" --delay 1.2
{PY} "$D/scr_collect.py" lookup --ids "$D/inputs/shard_reviews_2.json" --terms "$D/inputs/shard_lookup_2.json" --delay 1.0
echo "[bot2] DONE"
''',
 3: f'''#!/bin/bash
# Bot3: 社区提问 + 榜单维度
set -u
D="{BASE}/采集器"
O="$D/out_bot3"; mkdir -p "$O"
export SCR_OUT="$O"
cd "$D"
echo "[bot3] Apple 社区提问采集"
{PY} "$D/scr_collect.py" community --queries "$D/inputs/shard_community_3.json" --delay 2.0
echo "[bot3] DONE"
''',
 4: f'''#!/bin/bash
# Bot4: 全量榜单 + 竞品详情补齐 + 社区补充
set -u
D="{BASE}/采集器"
O="$D/out_bot4"; mkdir -p "$O"
export SCR_OUT="$O"
cd "$D"
echo "[bot4] 全分类榜单"
{PY} "$D/scr_collect.py" charts --all_genres --delay 0.6
echo "[bot4] DONE"
''',
}
for i, s in SCRIPTS.items():
    p = f"{BOT_DIR}/bot{i}.sh"
    with open(p, "w") as f:
        f.write(s)
    os.chmod(p, 0o755)
    print(f"写出 {p}")
print("完成")
