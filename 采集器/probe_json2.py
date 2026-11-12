import re, json, urllib.request
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
def get(u):
    return urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent": UA}), timeout=40).read().decode("utf-8","ignore")

for aid, label in [("1443835927","Outdoorsy"), ("1275803975","RV LIFE")]:
    html = get(f"https://apps.apple.com/us/app/id{aid}?see-all=reviews")
    m = re.search(r'<script[^>]*type="application/json"[^>]*>(.*?)</script>', html, re.S)
    blob = json.loads(m.group(1))
    items = blob["data"][0]["data"]["shelfMapping"]["allProductReviews"]["items"]
    print("="*70)
    print(f"{label} ({aid})  items={len(items)}")
    r0 = items[0]
    print("  review 字段:", list(r0.keys()))
    print("  样例1:", json.dumps(r0, ensure_ascii=False)[:900])
    print()
    # 提取所有评论的关键字段
    rows = []
    for it in items:
        rv = it.get("review") or {}
        rows.append({
            "id": rv.get("id"),
            "stars": rv.get("rating"),
            "date": (rv.get("date") or "")[:10],
            "title": (rv.get("title") or "").strip(),
            "body": (rv.get("body") or "").strip(),
            "author": ((rv.get("author") or {}).get("name") or "").strip(),
        })
    from collections import Counter
    print("  星级分布:", dict(Counter(r["stars"] for r in rows)))
    print("  有正文:", sum(1 for r in rows if r["body"]), "/", len(rows))
    print("  有标题:", sum(1 for r in rows if r["title"]), "/", len(rows))
    print("  去重 id 数:", len(set(r["id"] for r in rows)))
    print("  日期范围:", min(r["date"] for r in rows), "~", max(r["date"] for r in rows))
    for r in rows[:4]:
        print(f"    {r['stars']}★ {r['date']} {r['author'][:18]:20} | {r['title'][:38]:40} | {r['body'][:50]}")
