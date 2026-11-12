"""
StackExchange 补采 v3 —— 直连（不走代理），3.5s 间隔
根因：代理出口 IP 被 SE 限流（error code 1015 / HTTP 429）；直连 quota 正常
"""
import json, os, time, urllib.request, urllib.parse, gzip
from datetime import datetime, timezone

# 关键：绕过代理
for v in ("https_proxy", "http_proxy", "HTTPS_PROXY", "HTTP_PROXY",
          "ALL_PROXY", "all_proxy"):
    os.environ.pop(v, None)
os.environ["NO_PROXY"] = "*"
os.environ["no_proxy"] = "*"

BASE = "/Users/maike/Desktop/iOS副业调研_2026-11-09/采集数据/community_v2_forum"
os.makedirs(BASE, exist_ok=True)
PATH = os.path.join(BASE, "forum.jsonl")

SITES = ["stackoverflow", "apple", "webapps", "travel", "outdoors", "gaming"]
QUERIES = [
    "ios app store", "app store subscription", "iphone app update",
    "app crashes ios", "icloud sync", "in-app purchase", "apple id account",
    "app store review", "ios backup restore", "xcode build error",
    "app store purchase not showing", "iphone data lost",
]
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36"
API = "https://api.stackexchange.com/2.3/search/advanced"

# 不走代理的 opener
opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))

fh = open(PATH, "a", encoding="utf-8")
seen, total, errs = set(), 0, []


def get(url):
    req = urllib.request.Request(url, headers={
        "User-Agent": UA, "Accept-Encoding": "gzip", "Accept": "application/json"})
    with opener.open(req, timeout=45) as r:
        data = r.read()
        if r.headers.get("Content-Encoding") == "gzip":
            data = gzip.decompress(data)
        return json.loads(data.decode("utf-8"))


for site in SITES:
    for q in QUERIES:
        params = urllib.parse.urlencode({
            "site": site, "order": "desc", "sort": "votes", "q": q,
            "pagesize": 30, "filter": "default"})
        url = f"{API}?{params}"
        try:
            d = get(url)
        except Exception as e:
            errs.append(f"{site}/{q}: {type(e).__name__} {str(e)[:70]}")
            print(f"  ! {site:14} {q[:26]:28} {type(e).__name__} {str(e)[:50]}", flush=True)
            time.sleep(5)
            continue
        if "error_message" in d:
            errs.append(f"{site}/{q}: API {d.get('error_message')}")
            print(f"  ! {site:14} {q[:26]:28} API {str(d.get('error_message'))[:50]}", flush=True)
            time.sleep(5)
            continue
        items = d.get("items", [])
        n_new = 0
        for it in items:
            qid = f"{site}:{it.get('question_id')}"
            if qid in seen:
                continue
            seen.add(qid)
            n_new += 1
            total += 1
            fh.write(json.dumps({
                "source": "stackexchange", "site": site, "query": q,
                "question_id": it.get("question_id"), "title": it.get("title"),
                "url": it.get("link"), "score": it.get("score"),
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
        print(f"  ok {site:14} {q[:26]:28} {len(items):3} (new {n_new:2}) "
              f"quota={d.get('quota_remaining')} total {total}", flush=True)
        time.sleep(3.5)

fh.close()
print(f"\nDONE {total} 条 -> {PATH}; 错误 {len(errs)}")
for e in errs[:40]:
    print("  ", e)
