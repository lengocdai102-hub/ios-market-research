"""
统一去重 + 权威数据集构建
问题: 多个采集任务(winners/creators/expanded)会撞到同一个 app, 造成跨文件重复
      之前 reports_all 的 "零重复" 是在单文件口径下成立的, 合并后不成立
做法: 以 review_id 为全局主键合并, 同 id 取字段最全的一条
输出: v3_reviews/reviews_master.jsonl (全局唯一) + 统计
"""
import json, os, glob
from collections import Counter, defaultdict

D = "/Users/maike/Desktop/iOS副业调研_2026-11-09/采集数据"
SRC = f"{D}/v3_reviews"
OUT = f"{SRC}/reviews_master.jsonl"

FIELDS = ["review_id","app_id","app_name","title","body","stars","version","date",
          "vote_sum","vote_count","author","source"]

master = {}
dups = Counter()
files = [f for f in sorted(glob.glob(f"{SRC}/reviews_*.jsonl"))
         if os.path.basename(f) != "reviews_master.jsonl"]  # 排除自身, 避免自合并
for p in files:
    n=0
    with open(p, encoding="utf-8") as f:
        for line in f:
            line=line.strip()
            if not line: continue
            try: r=json.loads(line)
            except: continue
            rid=str(r.get("review_id") or "")
            if not rid:
                rid = f"{r.get('app_id')}_{r.get('date')}_{hash(str(r.get('body')))}"
            n+=1
            rec = {k: r.get(k) for k in FIELDS}
            rec["_src_file"] = os.path.basename(p)
            old = master.get(rid)
            if old is None:
                master[rid]=rec
            else:
                dups[rid]+=1
                # 取字段更全的一条
                def score(x): return sum(1 for k in FIELDS if x.get(k) not in (None,"",[]))
                if score(rec) > score(old):
                    rec["_src_file"] = old["_src_file"] + "+" + os.path.basename(p)
                    master[rid]=rec
    print(f"  {os.path.basename(p):42s} {n:>7,}")

apps = defaultdict(list)
for rid, r in master.items():
    apps[str(r.get("app_id"))].append(r)

with open(OUT,"w",encoding="utf-8") as f:
    for rid, r in master.items():
        f.write(json.dumps(r, ensure_ascii=False)+"\n")

star_ct = Counter(r.get("stars") for r in master.values())
nonempty = sum(1 for r in master.values() if (r.get("body") or "").strip())
by_year = Counter(str(r.get("date") or "")[:4] for r in master.values())

print(f"\n=== 全局唯一评论: {len(master):,} 条 ===")
print(f"  覆盖 app: {len(apps)}")
print(f"  合并时消除的重复: {sum(dups.values()):,} (涉及 {len(dups)} 个 id)")
print(f"  正文非空: {nonempty:,} ({nonempty/len(master)*100:.2f}%)")
print(f"  星级分布: " + " / ".join(f"{k}★:{v:,}" for k,v in sorted(star_ct.items(), reverse=True)))
print(f"  年份分布: " + " / ".join(f"{k}:{v:,}" for k,v in sorted(by_year.items())))
print(f"\n  每个 app 评论数: 中位 {sorted(len(v) for v in apps.values())[len(apps)//2]}, "
      f"满500的 app: {sum(1 for v in apps.values() if len(v)>=500)}")

json.dump({"total": len(master), "apps": len(apps), "dups_removed": sum(dups.values()),
  "nonempty_body": nonempty, "star_dist": dict(star_ct), "by_year": dict(by_year),
  "apps_at_500": sum(1 for v in apps.values() if len(v)>=500),
  "files": [os.path.basename(x) for x in files],
  "note": "全局以 review_id 唯一。跨文件重复已在合并时消除。"},
  open(f"{D}/reviews_master_stats.json","w"), ensure_ascii=False, indent=1)
print("\n已写入 reviews_master.jsonl + reviews_master_stats.json")
