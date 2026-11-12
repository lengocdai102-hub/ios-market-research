"""
统一竞品池加载器 + 扩池后的全量重算
新池 (inputs/competitor_pool.json, 10312 个) 字段名与旧池 (_expanded_competitors.json, 895) 不同:
  app_id / app_name / seller / genre / price / rating_count / rating / desc
统一成标准字段后重跑: 开发者结构 / 定价 / 时间序列 / 赢家 / 机会矩阵
"""
import json, os, statistics, re
from collections import Counter, defaultdict
from datetime import datetime, timezone

BASE = "/Users/maike/Desktop/iOS副业调研_2026-11-09"
D = f"{BASE}/采集数据"
C = f"{BASE}/采集器"
NOW = datetime(2026, 11, 10, tzinfo=timezone.utc)

# ---------- 统一加载 ----------
def load_pool():
    """返回标准字段 list: {id,name,seller,genre,price,rc,avg,rel,upd,desc}"""
    rows = []
    p2 = f"{C}/inputs/competitor_pool.json"
    if os.path.exists(p2):
        for r in json.load(open(p2)):
            rows.append({
                "id": str(r.get("app_id") or ""),
                "name": r.get("app_name") or "",
                "seller": r.get("seller") or "",
                "genre": r.get("genre") or "",
                "price": r.get("price") or 0.0,
                "rc": r.get("rating_count") or 0,
                "avg": r.get("rating") or 0.0,
                "rel": None, "upd": None,
                "desc": r.get("desc") or "",
                "hit": r.get("query_hit") or "",
            })
    # 旧池有 releaseDate / currentVersionReleaseDate, 补进来
    old = f"{D}/_expanded_competitors.json"
    if os.path.exists(old):
        om = {str(k): v for k, v in json.load(open(old)).items()}
        for r in rows:
            o = om.get(r["id"])
            if o:
                r["rel"] = o.get("releaseDate")
                r["upd"] = o.get("currentVersionReleaseDate")
                r["avg"] = r["avg"] or o.get("averageUserRating") or 0.0
                r["price"] = r["price"] or o.get("price") or 0.0
    return rows

def parse(s):
    if not s: return None
    try: return datetime.fromisoformat(str(s).replace("Z","+00:00"))
    except: return None

rows = load_pool()
# 去重
seen = set(); uniq = []
for r in rows:
    if not r["id"] or r["id"] in seen: continue
    seen.add(r["id"]); uniq.append(r)
rows = uniq
print(f"统一竞品池: {len(rows)} 个（去重后）")
print(f"  零评分: {sum(1 for r in rows if r['rc']==0)} ({sum(1 for r in rows if r['rc']==0)/len(rows)*100:.1f}%)")
print(f"  评分量>100: {sum(1 for r in rows if r['rc']>100)}")
print(f"  有 releaseDate 的: {sum(1 for r in rows if r['rel'])}")

# ---------- 开发者判定 ----------
COMPANY_KW = ["llc","inc","ltd","corp","gmbh","plc","company","group","labs","studios",
              "technologies","software","systems","solutions","media","publishing","digital",
              "holdings","insurance","bank","university","association","foundation","church",
              "agency","networks","entertainment","ventures","capital","partners","studio",
              "mobile","app","tools","utilities","games","games,","interactive","world","llc."]
FIRSTNAME = set("thomas john david james robert mary linda chen wang smith johnson williams brown jones garcia miller davis martinez roberts clark lewis robinson walker hall allen young hernandez king wright lopez hill scott green adams baker gonzalez nelson carter mitchell perez roberts turner phillips campbell parker evans edwards collins stewart sanchez morris rogers reed cook morgan bell murphy bailey rivera cooper richardson".split())
PERSONAL_HINT = ["indie","solo","personal","by "]

def is_personal(seller, name=""):
    s = (seller or "").strip()
    if not s: return False
    low = s.lower()
    for k in COMPANY_KW:
        if k in low: return False
    parts = [p for p in low.replace(",", " ").split() if p]
    # 明确提示词
    for h in PERSONAL_HINT:
        if h in low: return True
    # 姓名模式: 2-3 段, 至少一段是常见名
    if len(parts) in (2, 3):
        if any(p in FIRSTNAME for p in parts): return True
        if all(p.isalpha() and 3 <= len(p) <= 13 for p in parts):
            # 排除常见单词组合
            COMMON = {"rv","camper","camp","van","pro","plus","mobile","app","lite","free","max","go","to","do","list","boater","boating","sailing","yacht","marine","fish","hunting","campfire","outdoor"}
            if not any(p in COMMON for p in parts): return True
    return False

for r in rows: r["personal"] = is_personal(r["seller"], r["name"])
npers = sum(1 for r in rows if r["personal"])
print(f"\n个人开发者: {npers} ({npers/len(rows)*100:.1f}%)")
print("  样本:", [(r["seller"], r["name"][:22]) for r in rows if r["personal"]][:8])

# ---------- 定价 ----------
paid = [r for r in rows if r["price"] > 0]
print(f"\n一次性付费 app: {len(paid)} ({len(paid)/len(rows)*100:.1f}%)")
if paid:
    ps = sorted(r["price"] for r in paid)
    print(f"  买断价: min ${ps[0]:.2f} 中位 ${statistics.median(ps):.2f} max ${ps[-1]:.2f}")
    buckets = Counter()
    for r in paid:
        p = r["price"]
        b = "$0-1" if p<1 else "$1-5" if p<5 else "$5-10" if p<10 else "$10-25" if p<25 else "$25-50" if p<50 else "$50+"
        buckets[b] += 1
    for b in ["$0-1","$1-5","$5-10","$10-25","$25-50","$50+"]:
        print(f"    {b:>8}: {buckets[b]:>5} ({buckets[b]/len(paid)*100:.1f}%)")

# ---------- 时间序列 ----------
td = [r for r in rows if parse(r["rel"])]
print(f"\n有时间序列样本: {len(td)}")
by_year = defaultdict(list)
for r in td:
    rel = parse(r["rel"])
    age = max(1, (NOW-rel).days/30.44)
    by_year[rel.year].append((r["rc"], r["rc"]/age))
print(f"{'年':>6} {'新app':>7} {'总评分':>13} {'中位评分':>9} {'月均获客中位':>13} {'≥100评分占比':>13}")
yseries = {}
for y in sorted(by_year):
    g = by_year[y]
    tot = sum(x[0] for x in g)
    med = statistics.median([x[0] for x in g])
    rpm = statistics.median([x[1] for x in g])
    p100 = sum(1 for x in g if x[0]>=100)/len(g)*100
    yseries[y] = {"n":len(g),"total":tot,"median":med,"rpm":round(rpm,4),"pct100":round(p100,1)}
    print(f"{y:>6} {len(g):>7} {tot:>13,} {med:>9.0f} {rpm:>13.3f} {p100:>12.1f}%")

# 近 12 月新进入
new = [r for r in td if parse(r["rel"]) >= datetime(2025,11,1,tzinfo=timezone.utc)]
tot_all_rc = sum(r["rc"] for r in td); tot_new_rc = sum(r["rc"] for r in new)
print(f"\n近12月新进入者: {len(new)} 个 ({len(new)/len(td)*100:.1f}% of {len(td)})")
if new:
    for thr in [1,10,100,1000]:
        print(f"  评分量 ≥{thr:>5}: {sum(1 for r in new if r['rc']>=thr):>5} ({sum(1 for r in new if r['rc']>=thr)/len(new)*100:.1f}%)")
    print(f"  评分合计占全池: {tot_new_rc/max(1,tot_all_rc)*100:.3f}%")

# ---------- 赢家 ----------
print("\n=== 个人开发者 评分量 TOP20 ===")
winners = sorted([r for r in rows if r["personal"]], key=lambda r:-r["rc"])[:20]
print(f"{'app':38s} {'评分':>9} {'均分':>5} {'开发者':26s} {'分类':16s} {'买断':>6}")
for r in winners:
    print(f"{r['name'][:37]:38s} {r['rc']:>9,} {r['avg']:>5.2f} {r['seller'][:25]:26s} {str(r['genre'])[:15]:16s} {r['price']:>6.2f}")

json.dump({
  "generated": NOW.isoformat(), "pool_size": len(rows),
  "zero_rating": sum(1 for r in rows if r["rc"]==0),
  "pct_zero": round(sum(1 for r in rows if r["rc"]==0)/len(rows)*100,1),
  "gt100": sum(1 for r in rows if r["rc"]>100),
  "personal": npers, "pct_personal": round(npers/len(rows)*100,1),
  "paid_count": len(paid), "paid_pct": round(len(paid)/len(rows)*100,1),
  "paid_price": {"min": min(r['price'] for r in paid), "median": round(statistics.median([r['price'] for r in paid]),2),
                 "max": max(r['price'] for r in paid)} if paid else {},
  "price_buckets": {b: buckets[b] for b in ["$0-1","$1-5","$5-10","$10-25","$25-50","$50+"]},
  "timeseries": {str(k): v for k,v in yseries.items()},
  "new_entrants_12m": {"n": len(new), "pct": round(len(new)/max(1,len(td))*100,1),
     "pct_of_ratings": round(tot_new_rc/max(1,tot_all_rc)*100,3),
     "thresholds": {str(t): round(sum(1 for r in new if r['rc']>=t)/max(1,len(new))*100,1) for t in [1,10,100,1000]}},
  "winners_top20": [{"name":r["name"],"seller":r["seller"],"ratings":r["rc"],"avg":r["avg"],
     "genre":r["genre"],"price":r["price"],"id":r["id"]} for r in winners],
}, open(f"{D}/pool_full_stats.json","w"), ensure_ascii=False, indent=1)
print("\n已写入 pool_full_stats.json")
