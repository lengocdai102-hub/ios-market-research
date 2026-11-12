import re, json, urllib.request
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
def get(u):
    return urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent": UA}), timeout=40).read().decode("utf-8","ignore")

html = get("https://apps.apple.com/us/app/id1443835927?see-all=reviews")
m = re.search(r'<script[^>]*type="application/json"[^>]*>(.*?)</script>', html, re.S)
blob = json.loads(m.group(1))
dd = blob["data"][0]["data"]

print("A. shelfMapping 全部 key")
for k, v in dd["shelfMapping"].items():
    n = len(v.get("items", [])) if isinstance(v, dict) else "-"
    print(f"  {k}: items={n}  其他键={[x for x in v.keys() if x!='items'] if isinstance(v,dict) else ''}")

print()
print("B. 每个含 reviews 的 shelf 的星级分布")
for k, v in dd["shelfMapping"].items():
    if not isinstance(v, dict): continue
    items = v.get("items") or []
    if not items: continue
    from collections import Counter
    st = Counter()
    ids = []
    for it in items:
        rv = it.get("review") or it.get("productReview") or {}
        if "rating" in rv: st[rv["rating"]] += 1
        if rv.get("id"): ids.append(rv["id"])
    if st:
        print(f"  {k}: n={len(items)} 星级={dict(sorted(st.items()))} 唯一id={len(set(ids))}")
        print(f"      顶层键: {list(v.keys())}")

print()
print("C. shelfOrderings 里有没有排序/分页参数")
so = dd.get("shelfOrderings", {})
for k, arr in list(so.items())[:6]:
    if isinstance(arr, list) and arr:
        print(f"  {k}: [{len(arr)}] 首元素键={list(arr[0].keys())}")
        print(f"      首元素: {json.dumps(arr[0], ensure_ascii=False)[:300]}")

print()
print("D. review 单条完整字段")
rv = dd["shelfMapping"]["allProductReviews"]["items"][0]["review"]
for k, v in rv.items():
    print(f"  {k}: {str(v)[:110]}")

print()
print("E. 是否存在更多页 / nextPage")
s = json.dumps(blob)
for pat in ["nextPage", "pageNumber", "continuation", "hasMore", "totalCount", "reviewCount", "pagination"]:
    f = re.findall(rf'"{pat}"\s*:\s*([^,}}]{{1,40}})', s)
    if f: print(f"  {pat}: {f[:6]}")
