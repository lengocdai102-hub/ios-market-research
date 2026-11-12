"""
深挖 B: 用权威 ratingCounts 重算痛点权重
关键修正: 之前痛点分析基于 helpfulReview 10条样本(负向偏置 10:1)
方法: 把样本痛点率 × (全量低星占比/样本低星占比) 做逆概率加权, 得到全量口径
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
    if not m: return None, None
    b = json.loads(m.group(1))
    dd = b["data"][0]["data"]
    items = dd.get("shelfMapping", {}).get("allProductReviews", {}).get("items", [])
    pr = dd.get("shelfMapping", {}).get("productRatings", {}).get("items", [])
    ratings = pr[0] if pr else None
    rows = []
    for it in items:
        rv = it.get("review") or {}
        rows.append({"stars": rv.get("rating"), "body": rv.get("contents") or "",
                     "date": (rv.get("date") or "")[:10]})
    return rows, ratings

# 痛点关键词表
PAIN = {
    "订阅/付费墙": ["subscription", "subscribe", "paywall", "pay wall", "premium",
                "trial", "paid version", "expensive", "price", "refund", "charged",
                "subscription fee", "cancel"],
    "UI易用性":    ["confusing", "hard to use", "difficult", "clunky", "intuitive",
                "user interface", "ui", "usability", "complicated", "awkward",
                "not user friendly", "messy", "clutter"],
    "崩溃/稳定性":   ["crash", "crashes", "crashed", "bug", "freeze", "freezing",
                "stuck", "error", "broken", "won't open", "force quit"],
    "客户支持":     ["support", "customer service", "no response", "reply",
                "contacted", "developer doesn't", "ignored", "email"],
    "登录/账号":    ["login", "sign in", "signin", "log in", "password", "account",
                "authentication", "can't sign"],
    "数据丢失/清空": ["lost my", "data loss", "lost all", "deleted", "wiped",
                "disappeared", "reset", "missing data", "lost everything"],
    "广告/推广":    ["ads", "advertisement", "advertising", "popup", "promo"],
    "离线/同步":    ["offline", "no internet", "sync", "wi-fi", "wifi", "connection",
                "doesn't work without"],
    "内容过期/过时": ["outdated", "out of date", "not updated", "old information",
                "no longer", "obsolete", "last update"],
    "兼容/设备":    ["ipad", "iphone", "device", "compatible", "version",
                "screen size", "not working on"],
}

def classify(body):
    b = (body or "").lower()
    return {k: sum(1 for kw in v if kw in b) for k, v in PAIN.items() if any(kw in b for kw in v)}

meta = {}
for b in ["out_bot1", "out_bot2"]:
    p = f"{BASE}/采集器/{b}/review_targets_meta.json"
    if os.path.exists(p):
        for x in json.load(open(p)): meta[str(x["app_id"])] = x

cands = sorted(meta.items(), key=lambda kv: -(kv[1].get("rating_count") or 0))[:40]
print("=" * 80)
print("深挖B: 逆概率加权 —— 用全量分布校准 helpfulReview 样本的痛点权重")
print("=" * 80)
print(f"{'App':30} {'样本低星%':>9} {'全量低星%':>9} {'权重':>7} {'样本低星n':>9}")
print("-" * 80)

rows = []
for aid, m in cands:
    try:
        rv, ratings = json_reviews(aid)
        if not rv or not ratings: continue
        counts = ratings.get("ratingCounts") or []
        total = ratings.get("totalNumberOfRatings") or 0
        if not counts or not total: continue
        c = Counter(r["stars"] for r in rv)
        n = len(rv)
        s_low = (c[1] + c[2]) / n
        a_low = (counts[4] + counts[3]) / total
        if s_low == 0: continue
        w = a_low / s_low          # 加权系数: 样本低星越多 -> 真实低星占比越低 -> 权重<1
        rows.append({"app": m.get("app_name"), "aid": aid, "n": n,
                     "s_low": s_low, "a_low": a_low, "w": w,
                     "reviews": rv, "counts": counts, "total": total})
        print(f"  {str(m.get('app_name'))[:28]:30} {s_low*100:>8.1f}% {a_low*100:>8.1f}% {w:>6.3f}x {c[1]+c[2]:>9}")
        time.sleep(0.4)
    except Exception as e:
        print(f"  {aid} ERR {str(e)[:45]}")

if not rows:
    raise SystemExit("无数据")

print()
print("=" * 80)
print("痛点权重对比: 原始样本 vs 逆概率加权后")
print("=" * 80)

raw_cnt = Counter()
wgt_cnt = Counter()
for r in rows:
    for rv in r["reviews"]:
        if rv["stars"] and rv["stars"] <= 2:      # 只统计低星评论的痛点
            for k in classify(rv["body"]):
                raw_cnt[k] += 1
                wgt_cnt[k] += r["w"]

total_low = sum(raw_cnt.values()) or 1
print(f"  低星评论样本总数(带痛点标签的): {total_low}")
print(f"  {'痛点':16} {'原始条数':>8} {'原始%':>7} {'加权条数':>9} {'加权%':>7} {'变化':>8}")
print("-" * 80)
out = []
for k in sorted(raw_cnt, key=lambda x: -raw_cnt[x]):
    rp = raw_cnt[k] / total_low * 100
    wp = wgt_cnt[k] / total_low * 100
    delta = (wp / rp - 1) * 100 if rp else 0
    print(f"  {k:16} {raw_cnt[k]:>8} {rp:>6.1f}% {wgt_cnt[k]:>9.1f} {wp:>6.1f}% {delta:>+7.1f}%")
    out.append({"pain": k, "raw_n": raw_cnt[k], "raw_pct": round(rp, 2),
                "weighted_n": round(wgt_cnt[k], 1), "weighted_pct": round(wp, 2),
                "change_pct": round(delta, 1)})

json.dump({"apps": [{"app": r["app"], "aid": r["aid"], "sample_low_pct": round(r["s_low"]*100, 1),
                     "all_low_pct": round(r["a_low"]*100, 1), "weight": round(r["w"], 3),
                     "total_ratings": r["total"], "rating_counts": r["counts"]} for r in rows],
          "pain_weights": out},
          open(f"{D}/deepdive_pain_weighted.json", "w"), ensure_ascii=False, indent=2)
print(f"\n  -> {D}/deepdive_pain_weighted.json")
