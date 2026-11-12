"""查清内嵌 JSON 的 review 结构"""
import re, json, urllib.request

UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"

def get(u):
    return urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent": UA}), timeout=40).read().decode("utf-8", "ignore")

html = get("https://apps.apple.com/us/app/id1443835927?see-all=reviews")

m = re.search(r'<script[^>]*type="application/json"[^>]*>(.*?)</script>', html, re.S)
blob = json.loads(m.group(1))

def walk(o, path="", depth=0, out=None):
    if out is None: out = []
    if depth > 7: return out
    if isinstance(o, dict):
        for k, v in o.items():
            if k.lower() in ("review", "reviews", "userreview", "userreviews"):
                out.append((path + "/" + k, type(v).__name__, len(v) if hasattr(v, "__len__") else "-"))
            walk(v, path + "/" + k, depth + 1, out)
    elif isinstance(o, list):
        for i, v in enumerate(o[:3]):
            walk(v, f"{path}[{i}]", depth + 1, out)
    return out

hits = walk(blob)
print("含 review 键的路径:")
for p, t, n in hits[:20]:
    print(f"  {p}  ({t}, len={n})")

print()
print("=== 顶层 data 数组长度:", len(blob.get("data", [])))
d0 = blob["data"][0]
print("data[0].intent.id:", d0.get("intent", {}).get("id"))
dd = d0.get("data", {})
print("data[0].data 顶层键:", list(dd.keys())[:25])

so = dd.get("shelfOrderings")
if so:
    print("\nshelfOrderings 类型:", type(so).__name__)
    sk = list(so.keys()) if isinstance(so, dict) else None
    print("  keys:", sk[:8] if sk else "list")
    if isinstance(so, dict):
        for k in sk[:2]:
            v = so[k]
            print(f"  --- {k}: {type(v).__name__}")
            if isinstance(v, dict): print("      子键:", list(v.keys())[:12])

# 直接找 reviews 数组
def find_reviews(o, path="", depth=0):
    res = []
    if depth > 8: return res
    if isinstance(o, dict):
        for k, v in o.items():
            if k in ("reviews", "userReviews") and isinstance(v, list):
                res.append((path + "/" + k, v))
            res += find_reviews(v, path + "/" + k, depth + 1)
    elif isinstance(o, list):
        for i, v in enumerate(o[:4]):
            res += find_reviews(v, f"{path}[{i}]", depth + 1)
    return res

rv = find_reviews(blob)
print("\nreviews 数组:")
for p, arr in rv:
    print(f"  {p}  len={len(arr)}")
    if arr:
        print("  样例键:", list(arr[0].keys()))
        print("  样例:", json.dumps(arr[0], ensure_ascii=False)[:600])
