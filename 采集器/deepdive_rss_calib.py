"""
深挖 D: 验证 RSS 文字评论源的口径 —— 是真实差异还是端点偏差?
方法: 对每个 app 同时取
  A) RSS 文字评论的星级分布 (来自 v3_reviews/reviews_all.jsonl)
  B) 网页权威 ratingCounts (ratingCounts[4]/total = 1星占比)
对比两者。若差异在所有 app 上一致且巨大 -> 端点偏差;
若差异随 app 变化且与"打分人数远多于写字人数"相关 -> 真实的选择性偏差。
"""
import json, os, re, urllib.request, time
from collections import Counter, defaultdict

BASE = "/Users/maike/Desktop/iOS副业调研_2026-11-09"
D = f"{BASE}/采集数据"
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")

def get(u, tries=3):
    for i in range(tries):
        try:
            return urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent": UA}), timeout=40).read().decode("utf-8", "ignore")
        except Exception as e:
            if i == tries - 1: return None
            time.sleep(1.2 * (i + 1))
    return None

def auth_ratings(aid):
    h = get(f"https://apps.apple.com/us/app/id{aid}?see-all=reviews")
    if not h: return None
    m = re.search(r'<script[^>]*type="application/json"[^>]*>(.*?)</script>', h, re.S)
    if not m: return None
    try:
        b = json.loads(m.group(1))
        pr = b["data"][0]["data"]["shelfMapping"]["productRatings"]["items"][0]
    except Exception:
        return None
    return pr

# 1) 读 RSS 采集结果
path = f"{D}/v3_reviews/reviews_all.jsonl"
if not os.path.exists(path):
    raise SystemExit(f"未找到 {path}")
byapp = defaultdict(list)
n = 0
for line in open(path):
    try:
        r = json.loads(line); byapp[r["app_id"]].append(r); n += 1
    except Exception: pass
print(f"RSS 采集: {n} 条评论, 覆盖 {len(byapp)} 个 app")

# 2) 逐 app 取权威 ratingCounts 并对比
print()
print("=" * 96)
print(f"{'App':38} {'打分总数':>9} {'写字数':>7} {'写字率':>7} | {'权威1星%':>8} {'RSS 1星%':>8} {'差倍数':>7}")
print("-" * 96)
rows = []
for aid, rv in byapp.items():
    if len(rv) < 8: continue
    pr = auth_ratings(aid)
    if not pr: continue
    counts = pr.get("ratingCounts") or []
    total = pr.get("totalNumberOfRatings") or 0
    if not counts or not total: continue
    a_1 = counts[4] / total * 100
    st = Counter(r["stars"] for r in rv)
    r_1 = st[1] / len(rv) * 100
    ratio = (r_1 / a_1) if a_1 > 0 else float("inf")
    name = rv[0].get("app_name", "")[:36]
    rows.append({"aid": aid, "name": name, "ratings_total": total, "written": len(rv),
                 "write_rate": len(rv) / total * 100, "auth_1star_pct": round(a_1, 2),
                 "rss_1star_pct": round(r_1, 2), "ratio": round(ratio, 1) if a_1 > 0 else None,
                 "rss_dist": dict(st)})
    print(f"  {name:38} {total:>9} {len(rv):>7} {len(rv)/total*100:>6.2f}% | {a_1:>7.2f}% {r_1:>7.1f}% {ratio:>6.1f}x")
    time.sleep(0.35)

if rows:
    ratios = [r["ratio"] for r in rows if r["ratio"]]
    wr = [r["write_rate"] for r in rows]
    print()
    print(f"样本 {len(rows)} 个 app")
    print(f"  1星占比倍数 中位: {sorted(ratios)[len(ratios)//2]:.1f}x   区间 {min(ratios):.1f}x ~ {max(ratios):.1f}x")
    print(f"  写字率 中位: {sorted(wr)[len(wr)//2]:.3f}%   区间 {min(wr):.3f}% ~ {max(wr):.3f}%")
    # 相关性: 写字率 vs 1星倍数
    import statistics
    n_ = len(rows)
    mx = sum(r["ratio"] for r in rows if r["ratio"]) / n_
    my = sum(r["write_rate"] for r in rows) / n_
    cov = sum((r["write_rate"] - my) * ((r["ratio"] or 0) - mx) for r in rows)
    sx = statistics.pstdev([r["write_rate"] for r in rows]); sy = statistics.pstdev([(r["ratio"] or 0) for r in rows])
    corr = cov / (sx * sy) if sx and sy else 0
    print(f"  写字率 vs 1星倍数 相关系数: {corr:.3f}")
    print()
    if corr < -0.3:
        print("  => 写字率越低(打分人数远超写字人数)的 app, RSS 1星占比越偏离权威值")
        print("     => 说明 RSS 文字评论是【选择性样本】: 只有不满的用户才写字")
        print("     => 结论: RSS 的星级分布【不能】代表全量口碑, 但【正文内容】仍然有效")
    elif abs(corr) <= 0.3:
        print("  => 差异与写字率无强相关, 说明 RSS 星级分布存在系统性端点偏差")
    else:
        print("  => 差异与写字率正相关, 需进一步判断")

json.dump(rows, open(f"{D}/deepdive_rss_calibration.json", "w"), ensure_ascii=False, indent=2)
print(f"\n  -> {D}/deepdive_rss_calibration.json")
