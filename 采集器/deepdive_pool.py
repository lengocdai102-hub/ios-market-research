"""
深挖 E: RSS 评论池 vs 网页评分池 是否一致?
异常: 部分 app 的 RSS 评论数 > 总评分数 (RV Parks 231%, RV Owners Community 202%)
可能原因:
  A) RSS 返回所有历史文字评论(含已被移除/失效的), 而 ratingCounts 只统计当前有效打分
  B) RSS 混入其他 storefront(非美区) 评论
  C) ratingCounts 只统计打分, 不统计只写字不给星的 (不可能, Apple 评论必须给星)
验证方法:
  1. 网页 see-all 页面的 10 条评论 id 是否都出现在 RSS 集合里 (池子交集)
  2. 抽一个写字率>100% 的 app, 看它 RSS 评论的日期跨度 vs ratingCounts 的时间含义
  3. 用 iTunes Lookup API 对比 (第三个独立来源)
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
        except Exception:
            if i == tries - 1: return None
            time.sleep(1.2 * (i + 1))
    return None

# 载入 RSS 数据
byapp = defaultdict(list)
for line in open(f"{D}/v3_reviews/reviews_all.jsonl"):
    try:
        r = json.loads(line); byapp[r["app_id"]].append(r)
    except Exception: pass

comp = {str(c["trackId"]): c for c in json.load(open(f"{D}/dataset_competitors.json"))}

# 挑异常样本
odd, normal = [], []
for aid, rv in byapp.items():
    c = comp.get(aid)
    if not c: continue
    tot = c.get("userRatingCount") or 0
    if tot < 50: continue
    ratio = len(rv) / tot
    (odd if ratio > 1.0 else normal).append((aid, c["trackName"], len(rv), tot, ratio))

odd.sort(key=lambda x: -x[4]); normal.sort(key=lambda x: x[4])
print("=" * 92)
print("写字率 > 100% 的异常 app (RSS 评论数 > 总评分数):")
print("=" * 92)
for aid, name, n, tot, r in odd[:10]:
    print(f"  {name[:44]:46} RSS={n:>5} 总评分={tot:>7} 比率={r:.2f}x")
print()
print("写字率正常的 app (对照):")
for aid, name, n, tot, r in normal[:6]:
    print(f"  {name[:44]:46} RSS={n:>5} 总评分={tot:>7} 比率={r:.3f}x")

# 1) 池子交集检验
print()
print("=" * 92)
print("池子交集检验: 网页 see-all 页面的评论 id 是否都在 RSS 集合内")
print("=" * 92)
tests = [x[0] for x in odd[:3]] + [x[0] for x in normal[:3]]
for aid in tests:
    c = comp.get(aid); 
    h = get(f"https://apps.apple.com/us/app/id{aid}?see-all=reviews")
    if not h: print(f"  {aid}: 页面失败"); continue
    m = re.search(r'<script[^>]*type="application/json"[^>]*>(.*?)</script>', h, re.S)
    if not m: print(f"  {aid}: 无内嵌JSON"); continue
    b = json.loads(m.group(1))
    dd = b["data"][0]["data"]
    items = dd["shelfMapping"]["allProductReviews"].get("items", [])
    page_ids = set()
    for it in items:
        rv = it.get("review") or {}
        if rv.get("id"): page_ids.add(rv["id"])
    pr = dd["shelfMapping"]["productRatings"]["items"][0]
    rss_ids = {r["review_id"] for r in byapp.get(aid, [])}
    inter = page_ids & rss_ids
    # RSS id 格式与网页 id 格式对比
    ex_rss = next(iter(rss_ids)) if rss_ids else ""
    ex_page = next(iter(page_ids)) if page_ids else ""
    print(f"  {c['trackName'][:38]:40} 页面{len(page_ids)}条 ∩ RSS{len(rss_ids)}条 = {len(inter)} 命中")
    print(f"       页面id样例: {ex_page}")
    print(f"       RSS id样例: {ex_rss}")
    print(f"       权威 ratingCounts={pr.get('ratingCounts')} total={pr.get('totalNumberOfRatings')}")
    time.sleep(0.4)

# 2) 第三个独立来源: iTunes Lookup API
print()
print("=" * 92)
print("第三来源交叉核对: iTunes Lookup API 的 userRatingCount")
print("=" * 92)
for aid, name, n, tot, r in odd[:5]:
    h = get(f"https://itunes.apple.com/lookup?id={aid}&country=us")
    if not h: print(f"  {name}: lookup失败"); continue
    b = json.loads(h)
    res = b.get("results") or []
    if not res: print(f"  {name}: lookup无结果"); continue
    x = res[0]
    print(f"  {name[:40]:42} lookup评分={x.get('userRatingCount')}  平均={x.get('averageUserRating')}  "
          f"版本={x.get('version')}  发布={ (x.get('currentVersionReleaseDate') or '')[:10]}")
    time.sleep(0.3)
