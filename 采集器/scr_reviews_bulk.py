"""
批量采集: App Store 全量文字评论 (RSS 分页接口)
端点: https://itunes.apple.com/us/rss/customerreviews/page={N}/id={appid}/sortby=mostrecent/json
特性(已实测):
  - 每页 50 条, 可翻到该 app 评论总量为止 (Outdoorsy 463 条 = 全部文字评论)
  - 零重复 (review_id 唯一)
  - 带日期(updated) / 版本 / 投票数 / 正文
  - 评分量 22313 但文字评论仅 463 -> 大多数人只打分不写字
断点续爬: 已有 review_id 自动跳过
"""
import json, os, re, sys, time, threading, queue, urllib.request, urllib.error
from collections import Counter

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")
BASE = "/Users/maike/Desktop/iOS副业调研_2026-11-09"
D = f"{BASE}/采集数据"
OUT = f"{D}/v3_reviews"
os.makedirs(OUT, exist_ok=True)
LOCK = threading.Lock()
MAX_PAGE = 40          # 上限 2000 条
MIN_TAIL = 15          # 小于此数视为到底
WORKERS = 6


def get(u, tries=4):
    last = None
    for i in range(tries):
        try:
            return urllib.request.urlopen(
                urllib.request.Request(u, headers={"User-Agent": UA}), timeout=45
            ).read().decode("utf-8", "ignore")
        except Exception as e:
            last = e
            time.sleep(1.2 * (i + 1) + 0.3 * i)
    raise last


def parse_feed(h):
    try:
        b = json.loads(h)
    except Exception:
        return []
    ents = b.get("feed", {}).get("entry", [])
    if isinstance(ents, dict): ents = [ents]
    out = []
    for e in ents:
        if not isinstance(e.get("im:rating"), dict): continue
        def lab(x):
            return (x.get("label") if isinstance(x, dict) else x) or ""
        out.append({
            "review_id": lab(e.get("id")),
            "title": lab(e.get("title")).strip(),
            "body": lab(e.get("content")).strip(),
            "stars": int(lab(e.get("im:rating")) or 0),
            "version": lab(e.get("im:version")),
            "date": lab(e.get("updated"))[:10],
            "vote_sum": lab(e.get("im:voteSum")),
            "vote_count": lab(e.get("im:voteCount")),
            "url": (e.get("link", {}) or {}).get("attributes", {}).get("href", "") if isinstance(e.get("link"), dict) else "",
            "author": lab(e.get("author")),
        })
    return out


def collect(appid, name, fh, seen):
    got = 0
    for pg in range(1, MAX_PAGE + 1):
        u = (f"https://itunes.apple.com/us/rss/customerreviews/page={pg}/id={appid}"
             f"/sortby=mostrecent/json")
        try:
            h = get(u)
        except Exception as e:
            print(f"  [{appid}] p{pg} ERR {str(e)[:45]}", flush=True)
            break
        rows = parse_feed(h)
        if not rows:
            break
        new = []
        for r in rows:
            if not r["review_id"] or r["review_id"] in seen:
                continue
            seen.add(r["review_id"])
            r["app_id"] = appid
            r["app_name"] = name
            r["page"] = pg
            r["collected_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
            new.append(r)
        if new:
            with LOCK:
                for r in new:
                    fh.write(json.dumps(r, ensure_ascii=False) + "\n")
            got += len(new)
        if len(rows) < MIN_TAIL:
            break
        time.sleep(0.35)
    with LOCK:
        fh.flush()
    return got


def main():
    comp = json.load(open(f"{D}/dataset_competitors.json"))
    # 追加 196 竞品输入里的全部 id
    extra = []
    p = f"{BASE}/采集器/inputs/competitor_ids.json"
    if os.path.exists(p):
        extra = json.load(open(p))
    ids = {}
    for c in comp:
        ids[str(c["trackId"])] = c["trackName"]
    for e in extra:
        if isinstance(e, dict):
            aid = str(e.get("app_id") or e.get("trackId") or e.get("id") or "")
            if aid and aid not in ids:
                ids[aid] = e.get("app_name") or e.get("name") or aid
        elif isinstance(e, str):
            if e not in ids: ids[e] = e

    items = list(ids.items())
    print(f"待采集 App: {len(items)} 个", flush=True)

    outfile = f"{OUT}/reviews_all.jsonl"
    seen = set()
    if os.path.exists(outfile):
        for line in open(outfile):
            try: seen.add(json.loads(line)["review_id"])
            except Exception: pass
        print(f"断点续爬: 已有 {len(seen)} 条唯一评论", flush=True)

    fh = open(outfile, "a")
    q = queue.Queue()
    for x in items: q.put(x)
    stats = {"done": 0, "apps": 0, "new": 0, "zero": []}
    t0 = time.time()

    def worker():
        while True:
            try: aid, name = q.get_nowait()
            except queue.Empty: return
            try:
                n = collect(aid, name, fh, seen)
            except Exception as e:
                n = 0
                print(f"  [{aid}] FATAL {str(e)[:50]}", flush=True)
            with LOCK:
                stats["apps"] += 1
                stats["new"] += n
                if n == 0: stats["zero"].append(name)
                stats["done"] += 1
                if stats["done"] % 10 == 0:
                    el = time.time() - t0
                    print(f"  进度 {stats['done']}/{len(items)} app, 新增 {stats['new']} 条, "
                          f"{el:.0f}s, {stats['new']/max(el,1):.1f} 条/s", flush=True)
            q.task_done()

    ts = [threading.Thread(target=worker, daemon=True) for _ in range(WORKERS)]
    for t in ts: t.start()
    for t in ts: t.join()
    fh.close()

    print(f"\n完成: {stats['apps']} app, 新增 {stats['new']} 条评论")
    print(f"零评论 app: {len(stats['zero'])}")
    json.dump({"apps": stats["apps"], "new_reviews": stats["new"],
               "zero_review_apps": stats["zero"],
               "elapsed_sec": round(time.time() - t0, 1)},
              open(f"{OUT}/collect_stats.json", "w"), ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
