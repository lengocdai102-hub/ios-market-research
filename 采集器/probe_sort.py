import re, json, urllib.request
from collections import Counter
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
def get(u):
    return urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent": UA}), timeout=40).read().decode("utf-8","ignore")

def parse(html):
    m = re.search(r'<script[^>]*type="application/json"[^>]*>(.*?)</script>', html, re.S)
    if not m: return None
    b = json.loads(m.group(1))
    try:
        items = b["data"][0]["data"]["shelfMapping"]["allProductReviews"]["items"]
    except Exception:
        return None
    out = []
    for it in items:
        rv = it.get("review") or {}
        out.append((rv.get("rating"), rv.get("id"), (rv.get("title") or "")[:40]))
    return out

print("A. productRatings shelf 内容 (评分分布权威来源)")
html = get("https://apps.apple.com/us/app/id1443835927?see-all=reviews")
b = json.loads(re.search(r'<script[^>]*type="application/json"[^>]*>(.*?)</script>', html, re.S).group(1))
pr = b["data"][0]["data"]["shelfMapping"]["productRatings"]
print("  itemCount:", pr.get("itemCount"))
for it in pr.get("items", []):
    print("   ", json.dumps(it, ensure_ascii=False)[:800])

print()
print("B. seeAllAction / fetchStrategy (找排序与分页端点)")
for shelf in ["allProductReviews"]:
    sh = b["data"][0]["data"]["shelfMapping"][shelf]
    for k in ["seeAllAction","fetchStrategy","url","mergeWhenFetched","contentType","id","marker"]:
        print(f"  {shelf}.{k}: {json.dumps(sh.get(k), ensure_ascii=False)[:400]}")

print()
print("C. 试不同 sort/offset 参数")
base = "https://apps.apple.com/us/app/id1443835927"
for q in ["?see-all=reviews", "?see-all=reviews&sortBy=mostRecent", "?see-all=reviews&sort=mostRecent",
          "?see-all=reviews&offset=10", "?see-all=reviews&limit=50",
          "?see-all=reviews&platform=web&offset=10&limit=20"]:
    try:
        h = get(base + q)
        r = parse(h)
        if r is None: print(f"  {q:50} -> 无数据"); continue
        st = Counter(x[0] for x in r)
        ids = [x[1] for x in r]
        print(f"  {q:50} n={len(r):>3} 星级={dict(sorted(st.items()))} 唯一={len(set(ids))} 首id={ids[0] if ids else '-'}")
    except Exception as e:
        print(f"  {q:50} ERR {str(e)[:40]}")
