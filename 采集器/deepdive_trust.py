"""
深挖 H: 验证"换设备/多设备/订阅信任"这个最强信号
问题: 机会矩阵里"多设备/家庭共享"排第一, 但原声多是"换手机要重新付费"
      这是【平台政策问题】(Apple 换机不继承 IAP) 还是【开发者定价问题】?
      前者你无法防守, 后者可以。
方法: 对全量评论做精确定位, 分类每条相关评论属于哪类, 并统计开发者责任程度
"""
import json, os, re
from collections import Counter, defaultdict

BASE = "/Users/maike/Desktop/iOS副业调研_2026-11-09"
D = f"{BASE}/采集数据"

# 触发词
TRIG = ["new phone", "new iphone", "new ipad", "new device", "second phone", "new tablet",
        "upgrade phone", "changed phone", "switched to", "family sharing", "family share",
        "multiple devices", "other device", "my wife", "my husband", "both of us",
        "share with", "shared purchase", "don't have to buy again", "buy it again"]

# 责任分类
CAT = {
    "平台换机不继承IAP": ["new phone", "new iphone", "new ipad", "new device", "second phone",
                          "new tablet", "upgrade phone", "changed phone", "buy it again",
                          "don't have to buy again", "purchased again", "re-buy", "rebuy"],
    "家庭共享未启用": ["family sharing", "family share", "shared purchase", "share with"],
    "多设备不支持/不同步": ["multiple devices", "other device", "second device", "switched to",
                            "both of us", "my wife", "my husband", "both phones", "two devices"],
    "付费墙/强制订阅": ["subscription", "subscribe", "premium", "paywall", "upgrade", "paid version",
                        "now have to pay", "forced", "paid for", "one-time purchase", "lifetime"],
}

def load(path):
    byapp = defaultdict(list)
    for line in open(path):
        try:
            r = json.loads(line); byapp[r["app_id"]].append(r)
        except Exception: pass
    return byapp

def main():
    byapp = load(f"{D}/v3_reviews/reviews_all.jsonl")
    total = sum(len(v) for v in byapp.values())
    print("=" * 100)
    print(f"【深挖H】设备/付费信任信号全量分析  (样本 {total} 条评论 / {len(byapp)} app)")
    print("=" * 100)

    hits = []
    for aid, rv in byapp.items():
        for r in rv:
            t = (r.get("title", "") + " " + r.get("body", "")).lower()
            if any(k in t for k in TRIG):
                hits.append((aid, r))

    print(f"\n触发设备/家庭共享/重复付费的评论: {len(hits)} 条 ({len(hits)/total*100:.2f}% 的评论)")

    # 分类计数(一条可归多类)
    cls = Counter()
    cls_app = defaultdict(Counter)
    for aid, r in hits:
        t = (r.get("title", "") + " " + r.get("body", "")).lower()
        for c, kws in CAT.items():
            if any(k in t for k in kws):
                cls[c] += 1
                cls_app[c][r.get("app_name", "?")] += 1

    print("\n分类分布(可重叠):")
    for c, n in cls.most_common():
        print(f"  {c:<20} {n:>5} 条")
        for app, k in cls_app[c].most_common(5):
            print(f"       {app[:44]:46} {k}")

    # 关键区分: 平台问题 vs 开发者定价问题
    print()
    print("=" * 100)
    print("【关键区分】这能防守吗?")
    print("=" * 100)
    plat = cls.get("平台换机不继承IAP", 0)
    dev = cls.get("付费墙/强制订阅", 0)
    print(f"  A) 平台换机不继承 IAP: {plat} 条  -> 你无法防守(Apple 政策)")
    print(f"  B) 付费墙/强制订阅:     {dev} 条  -> 可防守(定价策略)")
    print(f"  B/(A+B) = {dev/(plat+dev)*100:.1f}%  -> 定价策略问题占比")

    # 定价偏好证据: 用户主动表达"愿意一次买断"
    print()
    print("=" * 100)
    print("【定价偏好证据】用户明确表达的一次性买断诉求")
    print("=" * 100)
    ONEOFF = ["lifetime", "one time purchase", "one-time purchase", "pay once", "buy it once",
              "pay once", "no subscription", "without subscription", "not a subscription",
              "single payment", "one off payment", "perpetual"]
    fam = defaultdict(list)
    n1 = 0
    for aid, rv in byapp.items():
        for r in rv:
            t = (r.get("title", "") + " " + r.get("body", "")).lower()
            if any(k in t for k in ONEOFF):
                n1 += 1
                fam[r.get("app_name", "?")].append(r)
    print(f"  明确提'一次买断/lifetime'的评论: {n1} 条 ({n1/total*100:.2f}%)")
    print(f"  涉及 app 数: {len(fam)}")
    print("\n  TOP10 app:")
    for app, rs in sorted(fam.items(), key=lambda x: -len(x[1]))[:10]:
        low = sum(1 for r in rs if r.get("stars",0) <= 2)
        print(f"    {app[:48]:50} {len(rs):>3} 条 (低星{low})")
    print("\n  样例原声:")
    shown = 0
    for app, rs in fam.items():
        for r in rs:
            if r.get("stars",0) <= 2 and len(r.get("body","")) > 60:
                print(f"    [{r['review_id']}] {r['stars']}星 {r['date']} {app[:34]}")
                print(f"      {r['title']}")
                print(f"      {r['body'][:230]}")
                shown += 1
                break
        if shown >= 8: break

    # 竞品里有多少做了一次性买断且成功
    print()
    print("=" * 100)
    print("【成功验证】哪些 app 做了 一次性买断 且评分量高? (这是模式验证)")
    print("=" * 100)
    pool = []
    p = f"{BASE}/采集器/inputs/competitor_pool.json"
    if os.path.exists(p):
        pool = json.load(open(p))
    iap = json.load(open(f"{D}/iap_prices_expanded.json"))["_apps"]
    # 找标题/描述里强调 lifetime/one-time 的 app
    for aid, a in iap.items():
        blob = ((a.get("trackName") or "") + " " + (a.get("description") or "")).lower()
        if ("lifetime" in blob or "one-time" in blob or "one time" in blob or "no subscription" in blob
                or "pay once" in blob) and (a.get("userRatingCount") or 0) > 300:
            print(f"    {a['trackName'][:44]:46} 评分量={a.get('userRatingCount'):>7}  "
                  f"平均={a.get('averageUserRating')}  IAP档位={a.get('iap_prices')}")
    # 一次性买断但 0/低评分
    print("\n  --- 声称买断但评分量低 (<200) 的, 看市场是否验证 ---")
    low = 0
    for aid, a in iap.items():
        blob = ((a.get("trackName") or "") + " " + (a.get("description") or "")).lower()
        if ("lifetime" in blob or "one-time" in blob or "pay once" in blob or "no subscription" in blob):
            rc = a.get("userRatingCount") or 0
            if rc < 200:
                low += 1
                if low <= 8:
                    print(f"    {a['trackName'][:44]:46} 评分量={rc:>6} 平均={a.get('averageUserRating')}")
    print(f"    (共 {low} 个)")

    json.dump({"total_reviews": total, "device_family_hits": len(hits),
               "categories": dict(cls),
               "oneoff_mentions": n1,
               "oneoff_apps": {k: len(v) for k, v in sorted(fam.items(), key=lambda x: -len(x[1]))[:30]},
               "oneoff_examples": [{"id": r["review_id"], "app": r.get("app_name"), "date": r.get("date"),
                                    "stars": r.get("stars"), "title": r.get("title"), "body": r.get("body")[:300]}
                                   for rs in list(fam.values())[:8] for r in rs[:1]]},
              open(f"{D}/deepdive_trust_signal.json", "w"), ensure_ascii=False, indent=2)
    print(f"\n  -> {D}/deepdive_trust_signal.json")


if __name__ == "__main__":
    main()
