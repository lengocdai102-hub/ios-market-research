#!/usr/bin/env python3
"""构建 ratingCounts 采集目标列表:
   A) reviews_master.jsonl 中出现次数最多的 TOP 300 app_id
   B) _expanded_competitors.json 的 895 个 app (上一条任务要求)
   合并去重, 优先已知名单的顺序, 输出 rating_targets.json
"""
import json, os, collections

BASE = "/Users/maike/Desktop/iOS副业调研_2026-11-09"
D = f"{BASE}/采集数据"

# A) TOP 300 by 评论条数
cnt = collections.Counter()
name = {}
p = f"{D}/v3_reviews/reviews_master.jsonl"
for line in open(p, encoding="utf-8"):
    line = line.strip()
    if line:
        try:
            r = json.loads(line)
        except Exception:
            continue
        aid = str(r.get("app_id") or "")
        if aid:
            cnt[aid] += 1
            name.setdefault(aid, r.get("app_name") or aid)
top300 = [a for a, _ in cnt.most_common(300)]

targets = []
seen = set()
for aid in top300:
    seen.add(aid)
    targets.append({"app_id": aid, "app_name": name.get(aid, aid),
                    "review_count": cnt[aid], "src": "master_top300"})

# B) expanded pool 895
exp = json.load(open(f"{D}/_expanded_competitors.json"))
n_exp_added = 0
for aid, x in exp.items():
    a = str(aid)
    if a in seen:
        continue
    seen.add(a)
    nm = x.get("trackName") or a if isinstance(x, dict) else a
    targets.append({"app_id": a, "app_name": nm,
                    "review_count": 0, "src": "expanded_895"})
    n_exp_added += 1

json.dump(targets, open(f"{D}/rating_targets.json", "w"), ensure_ascii=False, indent=1)
print(f"master 出现 app 总数: {len(cnt)}")
print(f"TOP300 来自 master, 新增 expanded: {n_exp_added}")
print(f"合计目标: {len(targets)}")
print("前 5:", [(t['app_id'], t['app_name'][:28], t['review_count']) for t in targets[:5]])
