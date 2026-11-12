"""
汇总所有 bot 的采集产出 -> 统一数据集 + 分析
在所有 bot 完成后运行: python3 aggregate.py
"""
import json, os, glob, re
from collections import Counter, defaultdict
from datetime import datetime

BASE = "/Users/maike/Desktop/iOS副业调研_2026-11-09"
OUT = f"{BASE}/采集数据"
os.makedirs(OUT, exist_ok=True)


def load_jsonl(path):
    rows = []
    if not os.path.exists(path): return rows
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line:
                try: rows.append(json.loads(line))
                except Exception: pass
    return rows


def load_json(path):
    try:
        with open(path) as f: return json.load(f)
    except Exception: return None


print("=" * 70)
print("App Store / Apple 社区 采集数据汇总")
print("生成时间:", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
print("=" * 70)

# ---------- 汇总评论 ----------
all_reviews = []
seen_r = set()
dist_map = {}
meta_map = {}
for d in sorted(glob.glob(f"{BASE}/采集器/out_bot*")):
    rv = load_jsonl(f"{d}/reviews.jsonl")
    for r in rv:
        k = (r.get("app_id"), r.get("date"), r.get("author"), str(r.get("body"))[:60])
        if k in seen_r: continue
        seen_r.add(k); all_reviews.append(r)
    dm = load_json(f"{d}/review_rating_distribution.json") or {}
    for aid, v in dm.items(): dist_map[aid] = v
    mm = load_json(f"{d}/review_targets_meta.json") or []
    for v in mm: meta_map[str(v.get("app_id"))] = v

print(f"\n【评论】去重后 {len(all_reviews)} 条，覆盖 {len(set(r.get('app_id') for r in all_reviews))} 个 app")

# ---------- 汇总竞品 ----------
all_comp = []
for d in sorted(glob.glob(f"{BASE}/采集器/out_bot*")):
    cp = load_jsonl(f"{d}/competitors.jsonl")
    all_comp.extend(cp)
uniq_c = {}
for c in all_comp:
    tid = c.get("trackId")
    if tid: uniq_c[tid] = c
print(f"【竞品详情】去重后 {len(uniq_c)} 个 app")

# ---------- 汇总榜单 ----------
all_charts = []
for d in sorted(glob.glob(f"{BASE}/采集器/out_bot*")):
    ch = load_jsonl(f"{d}/charts.jsonl")   # 只读正式文件, 跳过 *_backup.jsonl
    all_charts.extend(ch)
uc = {}
for c in all_charts:
    k = (c.get("chart"), c.get("genre_id"), c.get("app_id"))
    if k and k not in uc: uc[k] = c
all_charts = list(uc.values())
print(f"【排行榜】去重后 {len(all_charts)} 条，覆盖 {len(set(c.get('genre_name') for c in all_charts))} 个分类")

# ---------- 汇总社区 ----------
all_threads = []
for d in sorted(glob.glob(f"{BASE}/采集器/out_bot*")):
    th = load_jsonl(f"{d}/community_threads.jsonl")
    all_threads.extend(th)
ut = {}
for t in all_threads:
    tid = t.get("thread_id")
    if tid and tid not in ut: ut[tid] = t
all_threads = list(ut.values())
print(f"【社区提问】去重后 {len(all_threads)} 个帖子，覆盖 {len(set(t.get('query') for t in all_threads))} 个查询词")

# ---------- 统一数据集 ----------
json.dump(all_reviews, open(f"{OUT}/dataset_reviews.json", "w"), ensure_ascii=False, indent=2)
json.dump(list(uniq_c.values()), open(f"{OUT}/dataset_competitors.json", "w"), ensure_ascii=False, indent=2)
json.dump(all_charts, open(f"{OUT}/dataset_charts.json", "w"), ensure_ascii=False, indent=2)
json.dump(all_threads, open(f"{OUT}/dataset_community.json", "w"), ensure_ascii=False, indent=2)

# ---------- 分析 ----------
report = {}

# 1. 评星分布 + 低分痛点
star_counter = Counter()
for r in all_reviews:
    m = re.search(r"(\d)", r.get("stars") or "")
    if m: star_counter[int(m.group(1))] += 1
report["评论星级分布"] = dict(sorted(star_counter.items(), reverse=True))

low = [r for r in all_reviews if (lambda m: m and int(m.group(1)) <= 2)(re.search(r"(\d)", r.get("stars") or ""))]
report["低分评论条数"] = len(low)

# 2. 低分评论痛点关键词
PAIN = {
    "同步/云端故障": ["sync", "cloud", "server", "backup", "didn't sync", "not syncing", "lost data"],
    "订阅/付费墙": ["subscription", "subscribe", "paywall", "price", "charge", "refund", "expensive", "trial", "premium", "pay"],
    "登录/账号": ["login", "log in", "sign in", "account", "password", "sign up", "register", "reset"],
    "更新后崩溃": ["crash", "update", "version", "broke", "stopped working", "no longer works"],
    "UI/易用性": ["confusing", "hard to use", "intuitive", "interface", "ui", "layout", "cluttered", "useless", "difficult"],
    "数据丢失/清空": ["lost", "missing", "deleted", "wiped", "data loss", "empty", "reset everything"],
    "离线不可用": ["offline", "no internet", "airplane", "spotty", "reception"],
    "通知/提醒": ["notification", "reminder", "alert", "no reminder", "didn't remind"],
    "导入导出": ["import", "export", "csv", "pdf", "backup file", "transfer"],
    "客户支持": ["support", "customer service", "response", "email", "no reply", "contacted"],
}
pain_hits = {}
for cat, kws in PAIN.items():
    hits = []
    for r in low:
        t = ((r.get("title") or "") + " " + (r.get("body") or "")).lower()
        if any(k in t for k in kws): hits.append(r)
    if hits: pain_hits[cat] = len(hits)
report["低分评论痛点分布"] = dict(sorted(pain_hits.items(), key=lambda x: -x[1]))

# 3. 竞品下载量代理指标
comp_list = list(uniq_c.values())
def rc(x): return x.get("userRatingCount") or 0
comp_sorted = sorted(comp_list, key=lambda x: -rc(x))
report["竞品评分量Top20(下载量代理)"] = [
    {"name": c.get("trackName"), "id": c.get("trackId"), "ratings": rc(c),
     "avg": c.get("averageUserRating"), "genre": c.get("primaryGenreName"),
     "price": c.get("formattedPrice"), "seller": c.get("sellerName"),
     "released": (c.get("releaseDate") or "")[:10]}
    for c in comp_sorted[:20]]

# 4. 订阅/付费定价分布
paid = [c for c in comp_list if (c.get("price") or 0) > 0]
free = [c for c in comp_list if (c.get("price") or 0) == 0]
report["定价结构"] = {"付费": len(paid), "免费": len(free),
                      "付费中位价": sorted(c.get("price") for c in paid)[len(paid)//2] if paid else None,
                      "免费但有评分数>0": len([c for c in free if rc(c) > 0])}
prices = Counter()
for c in paid:
    p = c.get("price") or 0
    bucket = ("<=$2.99" if p <= 2.99 else "$3.99-$9.99" if p < 10 else
              "$10-$29.99" if p < 30 else "$30-$99.99" if p < 100 else ">=$100")
    prices[bucket] += 1
report["付费价格带分布"] = dict(prices)

# 5. 榜单中的房车/维护类 app
RV = re.compile(r"\bRV\b|camper|motorhome|caravan|overland|airstream|maintenance|boatoff|boat ", re.I)
chart_rv = [{"chart": c["chart"], "genre": c.get("genre_name"), "rank": c["rank"],
             "name": c["app_name"], "id": c.get("app_id")} for c in all_charts if RV.search(c.get("app_name") or "")]
chart_rv.sort(key=lambda x: x["rank"])
report["榜单中的房车/维护类app"] = chart_rv[:40]

# 6. 社区提问主题聚类
TOPIC = {
    "订阅取消/退款": ["cancel", "refund", "subscription", "trial", "charge", "billing", "payment", "cancelation"],
    "App Store 功能故障": ["not working", "crash", "update", "bug", "can't", "cannot", "issue", "problem", "error", "fail"],
    "购买/上架/审核": ["publish", "review", "reject", "approve", "developer", "sold", "sale", "account"],
    "搜索/发现": ["search", "find", "discover", "keyword", "ranking", "recommend"],
    "订阅疲劳/收费不满": ["scam", "ripoff", "too expensive", "scammed", "worst", "terrible", "uninstall", "refund"],
}
topic_hits = defaultdict(list)
for t in all_threads:
    title = (t.get("title") or "").lower()
    for topic, kws in TOPIC.items():
        if any(k in title for k in kws):
            topic_hits[topic].append(t)
report["社区提问主题分布"] = {k: len(v) for k, v in sorted(topic_hits.items(), key=lambda x: -len(x[1]))}
report["社区提问样本"] = {k: [x["title"][:120] for x in v[:8]] for k, v in topic_hits.items()}

# 8. 零评分/极低评分竞品 —— 新进入者聚集区(重要信号)
zero = [x for x in meta_map.values() if (x.get("rating_count") or 0) <= 5]
report["零评分竞品(评分量<=5)"] = {
    "数量": len(zero),
    "说明": "这些 App 已上架但评分量为0或极低, 表示 2026 年新进入者集中涌入且尚未获得用户验证。",
    "名单": [{"id": x.get("app_id"), "name": x.get("app_name"), "ratings": x.get("rating_count"),
              "genre": x.get("genre")} for x in sorted(zero, key=lambda y: -(y.get("rating_count") or 0))]
}

# 9. 竞品品类聚类 —— 名字关键词分组
CAT = {
    "调平/支撑(Leveling)": ["leveling", "leveler", "level ", "chocka", "levelr", "rigsteady", "camplerlevel", "blocks"],
    "检查清单(Checklist)": ["checklist", "check list", "ready2roam", "rigready", "ready"],
    "行程规划(Trip Planner)": ["trip planner", "trip planning", "route", "roamready", "rv ready", "itinerary"],
    "维护记录(Maintenance)": ["maintenance", "service", "repair", "vault", "keeper", "owner"],
    "地图/导航(Map/GPS)": ["map", "gps", "nav"],
    "露营/预订(Camping)": ["camping", "campground", "camp", "campspot", "koa", "hipcamp"],
    "买车/交易(Marketplace)": ["trader", "buy", "sell", "marketplace", "shop", "outdoorsy", "dyrt"],
}
cat_hits = defaultdict(list)
for x in meta_map.values():
    nm = (x.get("app_name") or "").lower()
    for cat, kws in CAT.items():
        if any(k in nm for k in kws):
            cat_hits[cat].append(x)
report["房车细分品类竞争度"] = {
    cat: {"数量": len(v),
          "评分量中位数": sorted([(y.get("rating_count") or 0) for y in v])[len(v)//2] if v else 0,
          "零评分占比": f"{len([y for y in v if (y.get('rating_count') or 0)<=5])}/{len(v)}"}
    for cat, v in sorted(cat_hits.items(), key=lambda x: -len(x[1]))
}

# 10. 大厂 vs 独立开发者
big = ["Google", "Apple", "Microsoft", "Amazon", "Yelp", "Angi", "NPS"]
report["开发者集中度"] = {
    "头部大厂app数": len([c for c in comp_list if any(b.lower() in (c.get("sellerName") or "").lower() for b in big)]),
    "独立/小开发者app数": len([c for c in comp_list if not any(b.lower() in (c.get("sellerName") or "").lower() for b in big)]),
    "头部评分数占比": f"{sum((c.get('userRatingCount') or 0) for c in comp_list if any(b.lower() in (c.get('sellerName') or '').lower() for b in big))} / {sum((c.get('userRatingCount') or 0) for c in comp_list)}"
}

report["下载量代理说明"] = {
    "口径": "Apple 不公开下载量。使用 userRatingCount(评分数) 作为主代理指标。",
    "经验系数_下载量约等于评分数的倍数": "美区 iOS 约 40-120 倍 (不同品类差异大, 需按品类标定)",
    "标定方法": "对同一分类内已知体量的 app, 用 userRatingCount / 排名位置交叉验证",
    "已采集的可用代理字段": ["userRatingCount", "averageUserRating", "榜单排名", "评论数", "版本更新频率", "上架时间"]
}

json.dump(report, open(f"{OUT}/analysis_report.json", "w"), ensure_ascii=False, indent=2)

# ---------- 打印摘要 ----------
print("\n" + "=" * 70)
print("分析摘要")
print("=" * 70)
print("\n1. 评论星级分布:", report["评论星级分布"])
print(f"   低分(<=2星)评论: {report['低分评论条数']} 条")
print("\n2. 低分痛点 Top:", json.dumps(report["低分评论痛点分布"], ensure_ascii=False))
print("\n3. 定价结构:", report["定价结构"])
print("   价格带:", json.dumps(report["付费价格带分布"], ensure_ascii=False))
print("\n4. 竞品评分量 Top10:")
for x in report["竞品评分量Top20(下载量代理)"][:10]:
    print(f"   {x['ratings']:>7} 评  ★{x['avg']}  {str(x['name'])[:38]:40} {x['genre']}")
print("\n5. 社区提问主题:", json.dumps(report["社区提问主题分布"], ensure_ascii=False))
print("\n6. 榜单中的房车/维护类 app (前15):")
for x in report["榜单中的房车/维护类app"][:15]:
    print(f"   {x['chart'][:14]:16} {x['genre'][:12]:14} #{x['rank']:<4} {x['name'][:38]}")
print(f"\n输出目录: {OUT}")
print("  dataset_reviews.json / dataset_competitors.json / dataset_charts.json / dataset_community.json")
print("  analysis_report.json")
