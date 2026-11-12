"""
扩展池评论采集: 对 895 个竞品池按 RSS 分页拉评论
- 先查已有 reviews_all.jsonl 的 app, 跳过
- 每个 app 最多 10 页 (500 条上限)
- 增量写入, 可断点续跑
"""
import json, os, sys, time, urllib.request, urllib.error

BASE = "/Users/maike/Desktop/iOS副业调研_2026-11-09"
D = f"{BASE}/采集数据"
OUT = f"{D}/v3_reviews/reviews_expanded.jsonl"
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")

pool = json.load(open(f"{D}/_expanded_competitors.json"))
have = set()
for p in [f"{D}/v3_reviews/reviews_all.jsonl", OUT]:
    if os.path.exists(p):
        for line in open(p, encoding="utf-8"):
            try:
                have.add(str(json.loads(line)["app_id"]))
            except Exception:
                pass
todo = [a for a in pool if str(a) not in have]
print(f"池 {len(pool)} / 已有评论 {len(have)} / 待采 {len(todo)}", flush=True)

def fetch(appid, page):
    url = (f"https://itunes.apple.com/us/rss/customerreviews/page={page}/id={appid}"
           f"/sortby=mostrecent/json")
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=25) as r:
        return json.loads(r.read().decode("utf-8", "ignore"))

fout = open(OUT, "a", encoding="utf-8")
new = 0; errs = 0; apps_done = 0
t0 = time.time()
for i, appid in enumerate(todo, 1):
    name = pool[appid].get("trackName", "?")
    got = 0
    for page in range(1, 11):
        try:
            d = fetch(appid, page)
        except urllib.error.HTTPError as e:
            if e.code == 400: break       # 超过上限
            errs += 1; break
        except Exception:
            errs += 1; break
        feed = (d.get("feed") or {})
        entries = feed.get("entry") or []
        if not entries: break
        # 第一条可能是 app 本身
        for e in entries:
            if not isinstance(e, dict): continue
            if "im:rating" not in e: continue
            # content 可能是 dict(有label) 或 纯字符串 —— 两种形态都处理
            _c = e.get("content")
            body = (_c.get("label") if isinstance(_c, dict) else _c) or ""
            _t = e.get("title")
            title = (_t.get("label") if isinstance(_t, dict) else _t) or ""
            _r = e.get("im:rating")
            stars = int((_r.get("label") if isinstance(_r, dict) else _r) or 0)
            _v = e.get("im:version")
            version = (_v.get("label") if isinstance(_v, dict) else _v) or ""
            _u = e.get("updated")
            date = (_u.get("label") if isinstance(_u, dict) else _u) or ""
            _vs = e.get("im:voteSum")
            vsum = (_vs.get("label") if isinstance(_vs, dict) else _vs) or "0"
            _vc = e.get("im:voteCount")
            vcnt = (_vc.get("label") if isinstance(_vc, dict) else _vc) or "0"
            _au = e.get("author")
            if isinstance(_au, dict):
                _n = _au.get("name")
                author = (_n.get("label") if isinstance(_n, dict) else _n) or ""
            else:
                author = ""
            _l = e.get("link")
            url = ""
            if isinstance(_l, dict):
                url = ((_l.get("attributes") or {}).get("href")) or _l.get("href") or ""
            _id = e.get("id")
            rid = (_id.get("label") if isinstance(_id, dict) else _id) or ""
            rec = {
                "review_id": str(rid),
                "app_id": str(appid), "app_name": name,
                "title": title,
                "body": body, "stars": stars,
                "version": version,
                "date": date[:10],
                "vote_sum": vsum, "vote_count": vcnt,
                "author": author,
                "url": url,
                "source": "apple_rss_customerreviews",
            }
            fout.write(json.dumps(rec, ensure_ascii=False) + "\n")
            new += 1; got += 1
        fout.flush()
        if len(entries) < 50: break
        time.sleep(0.35)
    apps_done += 1
    if i % 10 == 0 or got == 0:
        print(f"  [{i}/{len(todo)}] {name[:36]:38} +{got:<4} 累计新增 {new}  错 {errs}  "
              f"{time.time()-t0:.0f}s", flush=True)

fout.close()
print(f"\n完成: 新增 {new} 条, 处理 {apps_done} app, 错误 {errs}")
print(f"-> {OUT}")
