"""
深挖 J: 竞品时间序列 —— 赛道是在增长还是在萎缩？
思路: 用 895 竞品池的 releaseDate + currentVersionReleaseDate + userRatingCount 构造时间维度
  1) 按上架年份分桶: 每年新增 app 数 / 总评分数 / 平均分
  2) 判断: 新进入者是否还能拿到量? (老 app 涨评分, 新 app 涨不上去 = 赛道封闭)
  3) 近 12 个月上架的 app 里, 有多少拿到评分? (新进入成功率)
  4) 版本更新活跃度 (仍在维护 vs 已停更) —— 停更的 app 是"死位"
关键: 评分量是累计的, 要用"评分量 / 存活月数"算月均获客速度, 才能公平比较新老
"""
import json, os, statistics
from collections import Counter, defaultdict
from datetime import datetime, timezone

D = "/Users/maike/Desktop/iOS副业调研_2026-11-09/采集数据"
NOW = datetime(2026, 11, 10, tzinfo=timezone.utc)

pool = json.load(open(f"{D}/_expanded_competitors.json"))

def parse(s):
    if not s: return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except: return None

rows = []
for aid, a in pool.items():
    rel = parse(a.get("releaseDate"))
    upd = parse(a.get("currentVersionReleaseDate"))
    if not rel: continue
    age_m = max(1, (NOW - rel).days / 30.44)
    rc = a.get("userRatingCount") or 0
    rows.append({
        "id": aid, "name": a.get("trackName"), "rel": rel, "upd": upd,
        "age_m": age_m, "rc": rc,
        "rate_per_month": rc / age_m,
        "genre": a.get("primaryGenreName"),
        "seller": a.get("sellerName"),
        "avg": a.get("averageUserRating"),
    })
print(f"有效样本: {len(rows)} 个 app（总池 {len(pool)}）\n")

# ---- 1. 按上架年份 ----
by_year = defaultdict(list)
for r in rows: by_year[r["rel"].year].append(r)
print("=== 按上架年份 ===")
print(f"{'年':>6} {'新app':>7} {'总评分':>12} {'中位评分':>9} {'月均获客中位':>13} {'有量(≥100)':>10}")
for y in sorted(by_year):
    g = by_year[y]
    tot = sum(x["rc"] for x in g)
    med = statistics.median([x["rc"] for x in g])
    rpm = statistics.median([x["rate_per_month"] for x in g])
    win = sum(1 for x in g if x["rc"] >= 100)
    print(f"{y:>6} {len(g):>7} {tot:>12,} {med:>9.0f} {rpm:>13.3f} {win:>6} ({win/len(g)*100:.1f}%)")

# ---- 2. 新进入者能否拿到量 ----
print("\n=== 赛道开放度: 按存活月数看月均获客速度 ===")
buckets = [(0,6),(6,12),(12,24),(24,48),(48,120),(120,9999)]
print(f"{'区间(月)':>12} {'app数':>7} {'月均获客中位':>13} {'获客>0.5/月':>12} {'获客>5/月':>11}")
for lo,hi in buckets:
    g = [x for x in rows if lo <= x["age_m"] < hi]
    if not g: continue
    rpm = statistics.median([x["rate_per_month"] for x in g])
    a1 = sum(1 for x in g if x["rate_per_month"] > 0.5) / len(g) * 100
    a5 = sum(1 for x in g if x["rate_per_month"] > 5) / len(g) * 100
    print(f"{lo}-{hi if hi<9999 else '+'}".rjust(12) + f" {len(g):>7} {rpm:>13.3f} {a1:>11.1f}% {a5:>10.1f}%")

# ---- 3. 新进入者近12个月成功率 ----
print("\n=== 近 12 个月新进入者 (2025-11 之后上架) ===")
new = [x for x in rows if x["rel"] >= datetime(2025,11,1,tzinfo=timezone.utc)]
print(f"数量: {len(new)}")
for thr in [0, 1, 10, 100, 1000]:
    n = sum(1 for x in new if x["rc"] >= thr)
    print(f"  评分量 ≥ {thr:>5}: {n:>4} 个 ({n/len(new)*100:>5.1f}%)")
tot_new_rc = sum(x["rc"] for x in new)
tot_all_rc = sum(x["rc"] for x in rows)
print(f"  新进入者评分合计: {tot_new_rc:,}  占全池 {tot_new_rc/tot_all_rc*100:.2f}%")
print(f"  新进入者数量占比: {len(new)/len(rows)*100:.1f}%")

# ---- 4. 死位检测: 停更 app ----
print("\n=== 停更 / 死位检测 ===")
stale = [x for x in rows if x["upd"] and (NOW - x["upd"]).days > 365]
print(f"超过 12 个月未更新: {len(stale)} 个 ({len(stale)/len(rows)*100:.1f}%)")
alive = [x for x in rows if x["upd"] and (NOW - x["upd"]).days <= 180]
print(f"近 6 个月有更新(活跃): {len(alive)} 个 ({len(alive)/len(rows)*100:.1f}%)")
sa = [x for x in stale if x["rc"] >= 100]
print(f"  其中仍有 ≥100 评分的: {len(sa)} 个  ← 这些是'僵尸位但有用户粘性'")
# 僵尸位但仍有量 = 潜在可替代目标
zombie_hot = sorted([x for x in stale if x["rc"] >= 500], key=lambda z:-z["rc"])
print(f"\n  可被替代的高价值僵尸位 (停更>1年 且 ≥500评分): {len(zombie_hot)} 个")
for x in zombie_hot[:12]:
    print(f"    {x['name'][:40]:42s} 评分{x['rc']:>7,}  上架{x['rel'].year}  最后更新{x['upd'].strftime('%Y-%m')}")

# ---- 5. 分类趋势: 哪个品类在增长 ----
print("\n=== 品类时间趋势 (按上架年份的中位评分量) ===")
genre_year = defaultdict(list)
for r in rows: genre_year[(r["genre"], r["rel"].year)].append(r["rc"])
years = sorted(set(r["rel"].year for r in rows))
genres = [g for g,_ in Counter(r["genre"] for r in rows).most_common(12)]
print(f"{'品类':>18} " + " ".join(f"{y:>7}" for y in years[-6:]))
for g in genres:
    cells = []
    for y in years[-6:]:
        v = genre_year.get((g,y))
        cells.append(f"{statistics.median(v):>7.0f}" if v else f"{'-':>7}")
    print(f"{str(g)[:17]:>18} " + " ".join(cells))

out = {
    "generated": NOW.isoformat(),
    "sample_apps": len(rows),
    "by_release_year": {str(y): {
        "n": len(by_year[y]),
        "total_ratings": sum(x["rc"] for x in by_year[y]),
        "median_ratings": statistics.median([x["rc"] for x in by_year[y]]),
        "median_ratings_per_month": round(statistics.median([x["rate_per_month"] for x in by_year[y]]), 4),
        "pct_100plus": round(sum(1 for x in by_year[y] if x["rc"]>=100)/len(by_year[y])*100, 1),
    } for y in sorted(by_year)},
    "openness_buckets": [{"from_m": lo, "to_m": hi, "n": len([x for x in rows if lo<=x["age_m"]<hi]),
        "median_ratings_per_month": round(statistics.median([x["rate_per_month"] for x in rows if lo<=x["age_m"]<hi]),4),
        "pct_gt_0_5": round(sum(1 for x in rows if lo<=x["age_m"]<hi and x["rate_per_month"]>0.5)/max(1,len([x for x in rows if lo<=x["age_m"]<hi]))*100,1),
        "pct_gt_5": round(sum(1 for x in rows if lo<=x["age_m"]<hi and x["rate_per_month"]>5)/max(1,len([x for x in rows if lo<=x["age_m"]<hi]))*100,1),
    } for lo,hi in buckets if len([x for x in rows if lo<=x["age_m"]<hi])],
    "new_entrants_12m": {"n": len(new), "pct_of_apps": round(len(new)/len(rows)*100,1),
        "pct_of_ratings": round(tot_new_rc/tot_all_rc*100,2),
        "thresholds": {str(t): round(sum(1 for x in new if x["rc"]>=t)/len(new)*100,1) for t in [0,1,10,100,1000]}},
    "stale": {"n_over_1y": len(stale), "pct": round(len(stale)/len(rows)*100,1),
        "alive_6m": len(alive), "alive_pct": round(len(alive)/len(rows)*100,1),
        "hot_zombies": [{"name": x["name"], "ratings": x["rc"], "released": x["rel"].strftime("%Y-%m"),
            "last_update": x["upd"].strftime("%Y-%m")} for x in zombie_hot]},
    "genre_year_median": {g: {str(y): (round(statistics.median(genre_year[(g,y)])) if genre_year.get((g,y)) else None)
        for y in years} for g in genres},
}
json.dump(out, open(f"{D}/deepdive_timeseries.json","w"), ensure_ascii=False, indent=1)
print("\n已写入 deepdive_timeseries.json")
