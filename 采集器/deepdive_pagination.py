"""
深挖 C: 突破评论分页限制 (每 app 只有 10 条)
尝试路径:
  1. see-all=reviews 页面的 Next 按钮 -> 实际翻页参数
  2. 移动端 API (amp-api.apps.apple.com / pi-api.apps.apple.com)
  3. 不同 see-all 参数组合
目标: 把单 app 评论从 10 条提到 50+ 条
"""
import json, re, urllib.request, urllib.error, time

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")
TEST_AID = "1443835927"   # Outdoorsy - Rent an RV (22313 评分)

def get(u, hdr=None):
    h = {"User-Agent": UA, "Accept-Language": "en-US,en;q=0.9"}
    if hdr: h.update(hdr)
    return urllib.request.urlopen(urllib.request.Request(u, headers=h), timeout=40).read().decode("utf-8", "ignore")

def parse_reviews(html):
    m = re.search(r'<script[^>]*type="application/json"[^>]*>(.*?)</script>', html, re.S)
    if not m: return [], {}
    b = json.loads(m.group(1))
    try:
        dd = b["data"][0]["data"]
    except Exception:
        return [], {}
    items = dd.get("shelfMapping", {}).get("allProductReviews", {}).get("items", [])
    rows = []
    for it in items:
        rv = it.get("review") or {}
        if rv.get("id"):
            rows.append({"id": rv["id"], "stars": rv.get("rating"),
                         "date": (rv.get("date") or "")[:10],
                         "body": (rv.get("contents") or "")[:80]})
    pr = dd.get("shelfMapping", {}).get("productRatings", {}).get("items", [])
    ratings = pr[0] if pr else {}
    return rows, ratings

def show(tag, rows, extra=""):
    print(f"  {tag:52} {len(rows):>3} 条  {extra}")

print("=" * 82)
print(f"深挖C: 突破单app评论10条限制 (test app id={TEST_AID})")
print("=" * 82)

# 基线
base_html = get(f"https://apps.apple.com/us/app/id{TEST_AID}?see-all=reviews")
base_rows, base_rating = parse_reviews(base_html)
show("基线 see-all=reviews", base_rows, f"ratingCounts={base_rating.get('ratingCounts')}")
base_ids = {r["id"] for r in base_rows}

# 1) 找页面里的分页线索
print("\n[1] 页面分页线索扫描")
for kw in ["page", "offset", "limit", "pagination", "nextPage", "seeAllReviews",
           "allProductReviews", "sortBy", "sortOption", "pageNumber"]:
    hits = re.findall(rf'"{kw}"\s*:\s*([^,}}]{{1,60}})', base_html)
    if hits:
        uniq = list(dict.fromkeys(hits))[:5]
        print(f"  {kw:22} -> {uniq}")

# 2) 试各种 URL 参数组合
print("\n[2] URL 参数组合试探")
variants = [
    ("?see-all=reviews&page=2",        "see-all=reviews&page=2"),
    ("?see-all=reviews&page=3",        "see-all=reviews&page=3"),
    ("?see-all=reviews&sort=mostRecent","see-all=reviews&sort=mostRecent"),
    ("?see-all=reviews&sort=newest",   "see-all=reviews&sort=newest"),
    ("?see-all=reviews&sort=mostHelpful","see-all=reviews&sort=mostHelpful"),
    ("?see-all=reviews&platform=iphone","see-all=reviews&platform=iphone"),
    ("?see-all=reviews&limit=50",      "see-all=reviews&limit=50"),
    ("?see-all=reviews&type=recent",   "see-all=reviews&type=recent"),
]
for tag, q in variants:
    try:
        h = get(f"https://apps.apple.com/us/app/id{TEST_AID}{q}")
        r, _ = parse_reviews(h)
        new = len({x['id'] for x in r} - base_ids)
        show(tag, r, f"新增{new}条")
    except Exception as e:
        show(tag, [], f"ERR {str(e)[:30]}")
    time.sleep(0.5)

# 3) 看 JSON 里的完整 shelf / next 结构
print("\n[3] JSON 里 allProductReviews 的完整结构")
m = re.search(r'<script[^>]*type="application/json"[^>]*>(.*?)</script>', base_html, re.S)
b = json.loads(m.group(1))
dd = b["data"][0]["data"]
sm = dd.get("shelfMapping", {})
ar = sm.get("allProductReviews", {})
print(f"  allProductReviews keys: {list(ar.keys())}")
for k, v in ar.items():
    if k != "items":
        print(f"    {k} = {json.dumps(v, ensure_ascii=False)[:220]}")
print(f"\n  shelfMapping 全部 key: {list(sm.keys())}")

# 4) 顶层分页/翻页元信息
print("\n[4] 顶层 next/filter 线索")
for k in b.get("data", [{}])[0].get("data", {}).keys():
    print(f"  data.data key: {k}")
