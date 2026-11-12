import re, json, urllib.request
from collections import Counter
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
def get(u):
    return urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent": UA}), timeout=40).read().decode("utf-8","ignore")

def parse(html):
    m = re.search(r'<script[^>]*type="application/json"[^>]*>(.*?)</script>', html, re.S)
    if not m: return None, None
    b = json.loads(m.group(1))
    dd = b["data"][0]["data"]
    items = dd["shelfMapping"]["allProductReviews"]["items"]
    pr = dd["shelfMapping"]["productRatings"]["items"][0]
    rows = [(it["review"].get("rating"), it["review"].get("id"),
             (it["review"].get("date") or "")[:10]) for it in items]
    return rows, pr

print("A. 评论排序是不是严格按日期倒序")
for aid in ["1443835927", "1275803975", "6475045441"]:
    h = get(f"https://apps.apple.com/us/app/id{aid}?see-all=reviews")
    rows, pr = parse(h)
    dates = [r[2] for r in rows]
    desc = all(dates[i] >= dates[i+1] for i in range(len(dates)-1))
    print(f"  {aid}: n={len(rows)} 严格日期倒序={desc}")
    print(f"    日期序列: {dates}")

print()
print("B. productRatings.ratingCounts 权威分布 vs HTML 百分比宽度")
for aid in ["1443835927", "1275803975", "6755877370"]:
    h = get(f"https://apps.apple.com/us/app/id{aid}?see-all=reviews")
    rows, pr = parse(h)
    counts = pr.get("ratingCounts") or []
    tot = pr.get("totalNumberOfRatings")
    avg = pr.get("ratingAverage")
    print(f"  {aid}: avg={avg} total={tot}")
    print(f"    ratingCounts(5->1)={counts}  和={sum(counts) if counts else 0}")
    if counts and tot:
        print("    换算%: ", [f"{c/tot*100:.1f}%" for c in counts])
        # 加权平均校验
        w = sum((5-i)*c for i,c in enumerate(counts)) / sum(counts)
        print(f"    加权平均={w:.3f}  (与avg差 {abs(w-avg):.3f})")

print()
print("C. 分页真实端点探测 (AMP API 之外的路径)")
cands = [
 "https://apps.apple.com/us/app/id1443835927/reviews?page=2",
 "https://apps.apple.com/us/app/id1443835927?see-all=reviews&paginationToken=x",
]
for u in cands:
    try:
        r = urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent": UA}), timeout=25)
        print(f"  {u[:70]} -> {r.getcode()} len={len(r.read())}")
    except Exception as e:
        print(f"  {u[:70]} -> {str(e)[:60]}")
