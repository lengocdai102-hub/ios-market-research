"""
深挖 A: "最有帮助" 排序样本的代表性分析
问题: 每 app 只拿到 10 条 helpfulReview, 它代表全量口碑还是偏向极端?
方法: 用页面权威 ratingCounts 计算该 10 条在全量中的理论占比, 对比实际抓到的分布
"""
import json, os, re, urllib.request, time
from collections import Counter, defaultdict

BASE = "/Users/maike/Desktop/iOS副业调研_2026-11-09"
D = f"{BASE}/采集数据"
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")

def get(u):
    return urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent": UA}), timeout=45).read().decode("utf-8", "ignore")

def json_reviews(aid):
    h = get(f"https://apps.apple.com/us/app/id{aid}?see-all=reviews")
    m = re.search(r'<script[^>]*type="application/json"[^>]*>(.*?)</script>', h, re.S)
    if not m: return None, None, None
    b = json.loads(m.group(1))
    dd = b["data"][0]["data"]
    items = dd.get("shelfMapping", {}).get("allProductReviews", {}).get("items", [])
    pr = dd.get("shelfMapping", {}).get("productRatings", {}).get("items", [])
    ratings = pr[0] if pr else None
    rows = []
    for it in items:
        rv = it.get("review") or {}
        rows.append({"stars": rv.get("rating"), "date": (rv.get("date") or "")[:10],
                     "id": rv.get("id"), "help": (rv.get("body") or "")[:0]})
    return rows, ratings, h

# 取一批有代表性的 app
meta = {}
for b in ["out_bot1", "out_bot2"]:
    p = f"{BASE}/采集器/{b}/review_targets_meta.json"
    if os.path.exists(p):
        for x in json.load(open(p)): meta[str(x["app_id"])] = x

# 优先取评分量大的（样本代表性更好）
cands = sorted(meta.items(), key=lambda kv: -(kv[1].get("rating_count") or 0))[:14]
print("=" * 78)
print("深挖A: helpfulReview 10条样本 vs 全量分布 的代表性")
print("=" * 78)
print(f"{'App':34} {'总评分数':>8} {'样本':>4} {'样本低星%':>9} {'全量低星%':>9} {'代表倍数':>8}")

rows_out = []
for aid, m in cands:
    try:
        rv, ratings, _ = json_reviews(aid)
        if not rv or not ratings:
            continue
        counts = ratings.get("ratingCounts") or []
        total = ratings.get("totalNumberOfRatings")
        if not counts or not total:
            continue
        c = Counter(r["stars"] for r in rv)
        n = len(rv)
        sample_low = (c[1] + c[2]) / n * 100
        all_low = (counts[4] + counts[3]) / total * 100   # ratingCounts 是 5->1
        # 代表倍数: 样本10条相当于全量的多少个真实评分
        mult = n / (total / 100.0) if total else 0
        rows_out.append((m.get("app_name"), total, n, sample_low, all_low, mult))
        print(f"  {str(m.get('app_name'))[:32]:34} {total:>8} {n:>4} {sample_low:>8.1f}% {all_low:>8.1f}% {mult:>7.3f}x")
        time.sleep(0.5)
    except Exception as e:
        print(f"  {aid} ERR {str(e)[:50]}")

print()
if rows_out:
    hi = [r for r in rows_out if r[3] > r[4] + 5]
    lo = [r for r in rows_out if r[3] < r[4] - 5]
    same = [r for r in rows_out if abs(r[3] - r[4]) <= 5]
    print(f"  样本低星高于全量: {len(hi)} 个  |  低于全量: {len(lo)} 个  |  接近(±5pp): {len(same)} 个")
    print("  结论: " + (
        "helpfulReview 样本系统性偏向低分(负向偏置) —— 说明最刺眼的批评最容易被点『有用』而置顶"
        if len(hi) > len(lo) * 2 else
        "helpfulReview 样本无系统性偏置" if len(lo) > len(hi) * 2 else
        "helpfulReview 样本大致无偏(正负相当)"))
    print()
    print("  代表倍数含义: 10 条样本相当于全量评分的多少倍")
    print("  (倍数越小 = 每条样本代表的真实评分越多 = 样本越可靠)")
    for r in sorted(rows_out, key=lambda x: x[5])[:6]:
        print(f"    {str(r[0])[:30]:32} 总{r[1]:>7}评 -> 10条≈{r[5]:.3f}倍全量  可信度最高")

json.dump([{"app": r[0], "total": r[1], "n": r[2], "sample_low_pct": round(r[3], 2),
            "all_low_pct": round(r[4], 2), "sample_multiplier": round(r[5], 4)} for r in rows_out],
          open(f"{D}/deepdive_sample_representativeness.json", "w"), ensure_ascii=False, indent=2)
print(f"\n  -> {D}/deepdive_sample_representativeness.json")
