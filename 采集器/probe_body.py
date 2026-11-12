import re, json, urllib.request
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
def get(u):
    return urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent": UA}), timeout=40).read().decode("utf-8","ignore")

h = get("https://apps.apple.com/us/app/id1443835927?see-all=reviews")
b = json.loads(re.search(r'<script[^>]*type="application/json"[^>]*>(.*?)</script>', h, re.S).group(1))
items = b["data"][0]["data"]["shelfMapping"]["allProductReviews"]["items"]
print("A. 单条 review 全部字段")
rv = items[0]["review"]
for k, v in rv.items():
    print(f"  {k}: {str(v)[:120]}")
print()
print("B. contents 是否被截断 (看是否以句号/省略号结尾, 与 HTML 版对比)")
for it in items[:5]:
    rv = it["review"]
    c = rv.get("contents") or ""
    print(f"  id={rv.get('id')} len={len(c)} 尾40={c[-40:]!r}")
print()
print("C. impressionMetrics (排序依据?)")
for it in items[:3]:
    print(" ", json.dumps(it.get("impressionMetrics"), ensure_ascii=False)[:400])
print()
print("D. 是否有更多 review 字段藏在 HTML 而非 JSON (对比 body 长度)")
m = re.findall(r'aria-labelledby="review-(\d+)-title"', h)
print("  HTML 中 review id 数:", len(m), "唯一:", len(set(m)))
