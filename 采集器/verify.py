"""
交叉核验: 同一事实用多个独立来源对撞, 输出不一致清单
只用已采集数据 + 少量实时复查
"""
import json, os, re, urllib.request, time
from collections import defaultdict

BASE = "/Users/maike/Desktop/iOS副业调研_2026-11-09"
D = f"{BASE}/采集数据"
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"

reviews = json.load(open(f"{D}/dataset_reviews.json"))
comps = json.load(open(f"{D}/dataset_competitors.json"))
charts = json.load(open(f"{D}/dataset_charts.json"))
threads = json.load(open(f"{D}/dataset_community.json"))

# 采集时记录的 meta (来自 App Store 页面)
meta = {}
for b in ["out_bot1", "out_bot2"]:
    p = f"{BASE}/采集器/{b}/review_targets_meta.json"
    if os.path.exists(p):
        for x in json.load(open(p)):
            meta[str(x["app_id"])] = x

comp_by_id = {str(c.get("trackId")): c for c in comps}

print("=" * 72)
print("交叉核验报告")
print("=" * 72)

# ---------- 核验 1: 评分数 —— 页面 meta vs iTunes lookup ----------
print("\n【核验1】评分数一致性: App Store页面 meta  vs  iTunes lookup API")
both = [aid for aid in meta if aid in comp_by_id]
diff = []
for aid in both:
    a = meta[aid].get("rating_count") or 0
    b = comp_by_id[aid].get("userRatingCount") or 0
    if a != b:
        diff.append((aid, meta[aid].get("app_name"), a, b))
print(f"  可对比 app: {len(both)}  一致: {len(both)-len(diff)}  不一致: {len(diff)}")
for aid, nm, a, b in diff[:15]:
    print(f"    ! {aid} {str(nm)[:38]:40} 页面={a}  lookup={b}  差={b-a:+}")
if diff:
    print("  说明: 评分数随时间增长, 两次请求间隔内新增评分会造成偏差(方向应为 lookup>=页面)")

# ---------- 核验 2: 评分均值 ----------
print("\n【核验2】平均评分一致性")
d2 = []
for aid in both:
    a = meta[aid].get("avg_rating")
    b = comp_by_id[aid].get("averageUserRating")
    if a and b and abs(a - b) > 0.001:
        d2.append((aid, meta[aid].get("app_name"), a, b))
print(f"  一致: {len(both)-len(d2)}  不一致: {len(d2)}")
for x in d2[:10]: print(f"    ! {x[0]} {str(x[1])[:38]:40} 页面={x[2]} lookup={x[3]}")

# ---------- 核验 3: 评分分布反算 vs 总评分数 ----------
print("\n【核验3】评分分布反算人数 vs userRatingCount (关键: 分布百分比是否与总量自洽)")
ok = bad = 0
badlist = []
for aid, m in meta.items():
    dist = m.get("rating_dist_pct") or {}
    rc = m.get("rating_count") or 0
    if not dist or rc <= 0: continue
    s = sum(dist.values())
    if abs(s - 100) > 1.5:
        bad += 1; badlist.append((aid, m.get("app_name"), s, rc))
    else: ok += 1
print(f"  分布总和=100%: {ok}   不自洽: {bad}")
for x in badlist[:10]:
    print(f"    ! {x[0]} {str(x[1])[:38]:40} 分布和={x[2]:.1f}%  总评分数={x[3]}")

# ---------- 核验 4: 评论星级 vs 分布占比 ----------
print("\n【核验4】实抓评论星级占比 vs 页面分布(仅取到评论的app)")
cnt = defaultdict(lambda: defaultdict(int))
for r in reviews:
    m = re.search(r"(\d)", r.get("stars") or "")
    if m: cnt[str(r.get("app_id"))][int(m.group(1))] += 1
rows = []
for aid, c in cnt.items():
    if aid not in meta: continue
    tot = sum(c.values())
    if tot < 8: continue
    dist = meta[aid].get("rating_dist_pct") or {}
    if not dist: continue
    low_sample = (c[1] + c[2]) / tot * 100
    low_page = (float(dist.get("1", 0)) + float(dist.get("2", 0)))
    rows.append((aid, meta[aid].get("app_name"), tot, low_sample, low_page))
rows.sort(key=lambda x: -abs(x[3] - x[4]))
print(f"  可比 app: {len(rows)}")
print(f"  {'App':40} {'样本':>4} {'样本低星%':>9} {'页面低星%':>9} {'差':>7}")
for aid, nm, tot, s, p in rows[:14]:
    flag = " <<<" if abs(s - p) > 15 else ""
    print(f"    {str(nm)[:38]:40} {tot:>4} {s:>8.1f}% {p:>8.1f}% {s-p:>+6.1f}{flag}")
print("  解读: 服务端只给最新10-20条, 样本偏向近期, 与全量分布有差属正常;")
print("        但差>15个百分点说明近期口碑正在恶化或该app低星评论更易被顶起。")

# ---------- 核验 5: 榜单数据 vs 竞品池 ----------
print("\n【核验5】榜单中出现的 app 是否与竞品池重叠(交叉命中)")
chart_ids = set()
for c in charts:
    m = re.search(r"id(\d+)", str(c.get("url") or ""))
    if m: chart_ids.add(m.group(1))
pool_ids = set(comp_by_id) | set(meta)
print(f"  榜单去重 app_id: {len(chart_ids)}   竞品池 app_id: {len(pool_ids)}")
overlap = chart_ids & pool_ids
print(f"  交叉命中: {len(overlap)}")
for aid in list(overlap)[:20]:
    hits = [c for c in charts if re.search(rf"id{aid}\b", str(c.get("url") or ""))]
    best = min(hits, key=lambda x: x.get("rank", 999))
    print(f"    {aid} {str(comp_by_id.get(aid,{}).get('trackName'))[:34]:36} 最佳名次={best.get('rank')} {best.get('chart','')[:14]} {best.get('genre_name','')}")

# ---------- 核验 6: 社区帖 URL 有效性 ----------
print("\n【核验6】Apple 社区帖 URL 抽检 (10 条实时请求)")
import random
random.seed(7)
sample = random.sample(threads, min(10, len(threads)))
alive = 0
for t in sample:
    u = t.get("url") or ""
    try:
        req = urllib.request.Request(u, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=25) as r:
            code = r.getcode()
        if code == 200: alive += 1
        print(f"    {code}  {t.get('thread_id','')[:24]:26} {t.get('title','')[:46]}")
    except Exception as e:
        print(f"    ERR {t.get('thread_id','')[:24]:24} {str(e)[:34]} {t.get('title','')[:34]}")
    time.sleep(0.6)
print(f"  可访问: {alive}/{len(sample)}")

# ---------- 核验 7: 评论正文真实性抽查 ----------
print("\n【核验7】评论记录字段完整性")
bad_rev = 0
for r in reviews:
    if not r.get("body") or not r.get("stars") or not r.get("app_id"):
        bad_rev += 1
dates = [r.get("date") for r in reviews if r.get("date")]
print(f"  评论总数 {len(reviews)}  字段缺失 {bad_rev}")
print(f"  有日期的: {len(dates)}  日期范围: {min(dates) if dates else '-'} ~ {max(dates) if dates else '-'}")
if dates:
    y = defaultdict(int)
    for d in dates: y[str(d)[:4]] += 1
    print(f"  年份分布: {dict(sorted(y.items()))}")

print("\n" + "=" * 72)
