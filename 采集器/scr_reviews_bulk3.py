#!/usr/bin/env python3
"""
批量采集 App Store 全量文字评论 (RSS 分页), 支持断点续爬 + 分片并行 + 已完成 app 跳过。

端点: https://itunes.apple.com/us/rss/customerreviews/page={N}/id={appid}/sortby={sort}/json
实测事实(2026-11-10):
  - 每页 50 条, page1..page10, page11 返回 400 (Apple 硬上限)
  - 双排序合并: mostrecent (覆盖近期) + mosthelpful (覆盖早期历史), 单 app 上限 ~1000 条
  - RSS 分页偶发返回空页, 需重试
  - review_id 全局唯一

用法:
  scr_reviews_bulk3.py --shard bot1 --slice 0/8 [--min_rating N] [--workers N]
"""
import json, os, sys, time, threading, queue, urllib.request

BASE = "/Users/maike/Desktop/iOS副业调研_2026-11-09"
D = f"{BASE}/采集数据"
OUTDIR = f"{D}/v3_reviews"
DONE = f"{OUTDIR}/.done_apps.txt"
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")

MAX_PAGE = 10
MIN_TAIL = 15
SORTS = ["mostrecent", "mosthelpful"]
LOCK = threading.Lock()


def get(u, tries=3):
    last = None
    for i in range(tries):
        try:
            return urllib.request.urlopen(
                urllib.request.Request(u, headers={"User-Agent": UA}), timeout=40
            ).read().decode("utf-8", "ignore")
        except Exception as e:
            last = e
            time.sleep(0.8 * (i + 1))
    raise last


def parse_feed(h):
    try:
        b = json.loads(h)
    except Exception:
        return []
    ents = b.get("feed", {}).get("entry", [])
    if isinstance(ents, dict):
        ents = [ents]
    out = []
    for e in ents:
        if not isinstance(e.get("im:rating"), dict):
            continue

        def lab(x):
            return (x.get("label") if isinstance(x, dict) else x) or ""

        rid = lab(e.get("id"))
        if not rid:
            continue
        out.append({
            "review_id": rid,
            "title": lab(e.get("title")).strip(),
            "body": lab(e.get("content")).strip(),
            "stars": int(lab(e.get("im:rating")) or 0),
            "version": lab(e.get("im:version")),
            "date": lab(e.get("updated"))[:10],
            "vote_sum": lab(e.get("im:voteSum")),
            "vote_count": lab(e.get("im:voteCount")),
            "author": lab(e.get("author")),
            "url": (e.get("link", {}) or {}).get("attributes", {}).get("href", "")
                   if isinstance(e.get("link"), dict) else "",
        })
    return out


def collect(appid, name, fh, seen):
    got = 0
    for sort in SORTS:
        for pg in range(1, MAX_PAGE + 1):
            u = (f"https://itunes.apple.com/us/rss/customerreviews/page={pg}/id={appid}"
                 f"/sortby={sort}/json")
            rows = []
            for attempt in range(3):
                try:
                    rows = parse_feed(get(u, tries=2))
                except Exception:
                    rows = []
                if rows:
                    break
                time.sleep(0.7)
            if not rows:
                break
            new = []
            for r in rows:
                if r["review_id"] in seen:
                    continue
                seen.add(r["review_id"])
                r["app_id"] = appid
                r["app_name"] = name
                r["sort"] = sort
                r["page"] = pg
                r["collected_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
                new.append(r)
            if new:
                with LOCK:
                    for r in new:
                        fh.write(json.dumps(r, ensure_ascii=False) + "\n")
                    fh.flush()
                got += len(new)
            if len(rows) < MIN_TAIL:
                break
            time.sleep(0.15)
    return got


def build_pool(min_rating=0):
    ids, meta = {}, {}

    def add(aid, name, rc):
        if not aid:
            return
        if aid not in ids:
            ids[aid] = name or aid
            meta[aid] = rc or 0

    p = f"{BASE}/采集器/inputs/competitor_pool.json"
    if os.path.exists(p):
        for x in json.load(open(p)):
            rc = x.get("userRatingCount") or 0
            if rc >= min_rating:
                add(str(x.get("app_id") or x.get("trackId") or ""), x.get("app_name"), rc)
        print(f"  competitor_pool: {len(ids)}", flush=True)

    p = f"{BASE}/采集器/inputs/competitor_ids.json"
    if os.path.exists(p):
        for x in json.load(open(p)):
            if isinstance(x, dict):
                add(str(x.get("trackId") or x.get("app_id") or x.get("id") or ""),
                    x.get("trackName") or x.get("app_name"), x.get("userRatingCount"))
            else:
                add(str(x), str(x), None)
        print(f"  +competitor_ids: {len(ids)}", flush=True)

    p = f"{D}/dataset_competitors.json"
    if os.path.exists(p):
        for c in json.load(open(p)):
            add(str(c.get("trackId") or ""), c.get("trackName"), c.get("userRatingCount"))
        print(f"  +dataset_competitors: {len(ids)}", flush=True)

    for i in (1, 2, 3, 4):
        p = f"{BASE}/采集器/inputs/shard_reviews_{i}.json"
        if os.path.exists(p):
            for x in json.load(open(p)):
                if isinstance(x, dict):
                    add(str(x.get("app_id") or x.get("trackId") or x.get("id") or ""),
                        x.get("app_name") or x.get("trackName"), x.get("userRatingCount"))
                else:
                    add(str(x), str(x), None)
            print(f"  +shard_reviews_{i}: {len(ids)}", flush=True)

    for s in ("v2_bot1", "v2_bot2"):
        p = f"{D}/{s}/reviews.jsonl"
        if os.path.exists(p):
            for line in open(p, encoding="utf-8"):
                line = line.strip()
                if line:
                    r = json.loads(line)
                    add(str(r.get("app_id")), r.get("app_name"), None)
            print(f"  +{s}: {len(ids)}", flush=True)

    # 已有所有 v3_reviews 分片的 app
    for f in os.listdir(OUTDIR):
        if f.endswith(".jsonl"):
            for line in open(f"{OUTDIR}/{f}", encoding="utf-8"):
                line = line.strip()
                if line:
                    try:
                        r = json.loads(line)
                        add(str(r.get("app_id")), r.get("app_name"), None)
                    except Exception:
                        pass
    print(f"  +已有分片: {len(ids)}", flush=True)
    return ids, meta


def main():
    shard = "bot1"
    min_rating = 0
    sl_i, sl_n = 0, 1
    workers = 10
    args = sys.argv[1:]
    if "--shard" in args:
        shard = args[args.index("--shard") + 1]
    if "--min_rating" in args:
        min_rating = int(args[args.index("--min_rating") + 1])
    if "--slice" in args:
        a, b = args[args.index("--slice") + 1].split("/")
        sl_i, sl_n = int(a), int(b)
    if "--workers" in args:
        workers = int(args[args.index("--workers") + 1])

    out = f"{OUTDIR}/{shard}_reviews.jsonl"
    os.makedirs(OUTDIR, exist_ok=True)

    ids, meta = build_pool(min_rating)
    done = set()
    if os.path.exists(DONE):
        done = {l.strip() for l in open(DONE) if l.strip()}
    print(f"已完成 app 记录: {len(done)}", flush=True)

    items = [(a, n) for a, n in ids.items() if a not in done]
    items.sort(key=lambda kv: -(meta.get(kv[0]) or 0))
    if sl_n > 1:
        items = items[sl_i::sl_n]
    print(f"待采集: {len(items)} app (分片 {sl_i+1}/{sl_n}, workers={workers}) -> {out}", flush=True)

    seen = set()
    if os.path.exists(out):
        for line in open(out, encoding="utf-8"):
            line = line.strip()
            if line:
                try:
                    seen.add(json.loads(line)["review_id"])
                except Exception:
                    pass
    print(f"断点续爬: 已有 {len(seen)} 条唯一评论", flush=True)

    fh = open(out, "a", encoding="utf-8")
    donefh = open(DONE, "a", encoding="utf-8")
    q = queue.Queue()
    for x in items:
        q.put(x)
    st = {"apps": 0, "new": 0, "err": 0}
    t0 = time.time()

    def worker():
        while True:
            try:
                aid, name = q.get_nowait()
            except queue.Empty:
                return
            try:
                n = collect(aid, name, fh, seen)
            except Exception as e:
                n = 0
                with LOCK:
                    st["err"] += 1
                print(f"  [{aid}] FATAL {str(e)[:50]}", flush=True)
            with LOCK:
                st["apps"] += 1
                st["new"] += n
                donefh.write(aid + "\n")
                donefh.flush()
                if st["apps"] % 50 == 0:
                    el = time.time() - t0
                    print(f"  进度 {st['apps']}/{len(items)} app, 新增 {st['new']} 条, "
                          f"{el:.0f}s, {st['new']/max(el,1):.1f} 条/s", flush=True)
            q.task_done()

    ts = [threading.Thread(target=worker, daemon=True) for _ in range(workers)]
    for t in ts:
        t.start()
    for t in ts:
        t.join()
    fh.close()
    donefh.close()
    print(f"完成: {st['apps']} app, 新增 {st['new']} 条, 错误 {st['err']}, "
          f"用时 {time.time()-t0:.0f}s")


if __name__ == "__main__":
    main()
