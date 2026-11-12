"""
StackExchange 补采（低频 3.5s 间隔，无 key）
目标站点: stackoverflow, apple, webapps, travel, outdoors, gaming
"""
import json, os, time, urllib.request, urllib.parse, gzip, io
from datetime import datetime, timezone

BASE = "/Users/maike/Desktop/iOS副业调研_2026-11-09/采集数据/community_v2_forum"
os.makedirs(BASE, exist_ok=True)
PATH = os.path.join(BASE, "forum.jsonl")

SITES = ["stackoverflow", "apple", "webapps", "travel", "outdoors", "gaming"]
QUERIES = [
    "ios app store",
    "app store purchase",
    "app store subscription",
    "iphone app update",
    "app crashes ios",
    "icloud sync",
    "app store review",
    "in-app purchase",
    "apple id account",
    "ios backup restore",
    "xcode build error",
    "app store approval",
]

UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36"
API = "https://api.stackexchange.com/2.3/search/advanced"

fh = open(PATH, "a", encoding="utf-8")
seen = set()
total = 0
errs = []

def get(url):
    req = urllib.request.Request(url, headers={
        "User-Agent": UA, "Accept-Encoding": "gzip",
        "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=45) as r:
        data = r.read()
        if r.headers.get("Content-Encoding") == "gzip":
            data = gzip.decompress(data)
        return json.loads(data.decode("utf-8"))

for site in SITES:
    for q in QUERIES:
        params = urllib.parse.urlencode({
            "site": site, "order": "desc", "sort": "votes", "q": q,
            "pagesize": 30, "filter": "default",
        })
        url = f"{API}?{params}"
        try:
            d = get(url)
        except Exception as e:
            errs.append(f"{site}/{q}: {type(e).__name__} {str(e)[:80]}")
            print(f"  ! {site:15} {q[:28]:30} {type(e).__name__} {str(e)[:60]}", flush=True)
            time.sleep(4.0)
            continue
        if "error_message" in d:
            errs.append(f"{site}/{q}: API {d.get('error_message')}")
            print(f"  ! {site:15} {q[:28]:30} API {str(d.get('error_message'))[:60]}", flush=True)
            time.sleep(4.0)
            continue
        items = d.get("items", [])
        quota = d.get("quota_remaining")
        n_new = 0
        for it in items:
            qid = f"{site}:{it.get('question_id')}"
            if qid in seen:
                continue
            seen.add(qid)
            n_new += 1
            total += 1
            fh.write(json.dumps({
                "source": "stackexchange",
                "site": site,
                "query": q,
                "question_id": it.get("question_id"),
                "title": it.get("title"),
                "url": it.get("link"),
                "score": it.get("score"),
                "answer_count": it.get("answer_count"),
                "view_count": it.get("view_count"),
                "is_answered": it.get("is_answered"),
                "creation_date": it.get("creation_date"),
                "last_activity_date": it.get("last_activity_date"),
                "tags": it.get("tags"),
                "body_snippet": (it.get("body") or "")[:600],
                "collected_at": datetime.now(timezone.utc).isoformat(),
            }, ensure_ascii=False) + "\n")
        fh.flush()
        print(f"  ok {site:15} {q[:28]:30} {len(items):3} 条 (新 {n_new:2}) quota={quota} 累计 {total}", flush=True)
        time.sleep(3.5)

fh.close()
print(f"\n完成: {total} 条 -> {PATH}")
print(f"错误 {len(errs)} 条:")
for e in errs[:30]:
    print("  ", e)
