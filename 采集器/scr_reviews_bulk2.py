#!/usr/bin/env python3
"""
批量采集: App Store 全量文字评论 (RSS 分页接口)
端点: https://itunes.apple.com/us/rss/customerreviews/page={N}/id={appid}/sortby=mostrecent/json
已实测: 每页 50 条, page1..page10 = 最多 500 条 (page11 返回 400, Apple 硬上限)
零重复 (review_id 唯一), 严格日期倒序

输出: 采集数据/v3_reviews/<shard>.jsonl (与 reviews_all.jsonl 同目录, 不覆盖)
用法: scr_reviews_bulk2.py --shard bot1 [--out 采集数据/v3_reviews/bot1_reviews.jsonl]
"""
import json, os, re, sys, time, threading, queue, urllib.request

BASE = "/Users/maike/Desktop/iOS副业调研_2026-11-09"
D = f"{BASE}/采集数据"
OUTDIR = f"{D}/v3_reviews"
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")

MAX_PAGE = 10          # Apple 硬上限: page11 -> 400
MIN_TAIL = 15          # 本页少于该数视为到底
WORKERS = 10
SORTS = ["mostrecent", "mosthelpful"]   # 双排序合并: mostrecent 覆盖近期, mosthelpful 补早期历史
LOCK = threading.Lock()


def get(u, tries=4):
    last = None
    for i in range(tries):
        try:
            return urllib.request.urlopen(
                urllib.request.Request(u, headers={"User-Agent": UA}), timeout=45
            ).read().decode("utf-8", "ignore")
        except Exception as e:
            last = e
            time.sleep(1.0 * (i + 1) + 0.3 * i)
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

        out.append({
            "review_id": lab(e.get("id")),
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
    """抓一个 app 的全部文字评论。
    双排序 mostrecent + mosthelpful 合并, 覆盖全历史。
    实测: RSS 分页不稳(某页可能返回空), 空页重试 3 次再放弃。"""
    got = 0
    for sort in SORTS:
        for pg in range(1, MAX_PAGE + 1):
            u = (f"https://itunes.apple.com/us/rss/customerreviews/page={pg}/id={appid}"
                 f"/sortby={sort}/json")
            rows = []
            # 空页重试: RSS 偶发返回空, 重试可恢复
            for attempt in range(3):
                try:
                    h = get(u, tries=2)
                except Exception as e:
                    if attempt == 2:
                        print(f"  [{appid}] {sort} p{pg} ERR {str(e)[:40]}", flush=True)
                    time.sleep(0.8)
                    continue
                rows = parse_feed(h)
                if rows:
                    break
                time.sleep(0.8)
            if not rows:
                break
            new = []
            for r in rows:
                if not r["review_id"] or r["review_id"] in seen:
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
                got += len(new)
            if len(rows) < MIN_TAIL:
                break
            time.sleep(0.25)
    with LOCK:
        fh.flush()
    return got


def build_pool(min_rating=0):
    """合并所有来源的 app id -> name。min_rating 只对 competitor_pool 生效(按 userRatingCount 过滤)。"""
    ids = {}
    meta = {}
    # 1) competitor_pool.json (本轮生成的搜索大池)
    p = f"{BASE}/采集器/inputs/competitor_pool.json"
    if os.path.exists(p):
        for x in json.load(open(p)):
            aid = str(x.get("app_id") or x.get("trackId") or "")
            if aid and (x.get("userRatingCount") or 0) >= min_rating:
                ids[aid] = x.get("app_name") or aid
                meta[aid] = x.get("userRatingCount") or 0
        print(f"  competitor_pool: {len(ids)} (min_rating={min_rating})")
    # 2) competitor_ids.json (已有 196 个竞品输入)
    p = f"{BASE}/采集器/inputs/competitor_ids.json"
    if os.path.exists(p):
        for x in json.load(open(p)):
            if isinstance(x, dict):
                aid = str(x.get("trackId") or x.get("app_id") or x.get("id") or "")
                if aid and aid not in ids:
                    ids[aid] = x.get("trackName") or x.get("app_name") or aid
                    meta[aid] = x.get("userRatingCount") or 0
            elif isinstance(x, str) and x not in ids:
                ids[x] = x
                meta[x] = 0
        print(f"  +competitor_ids: {len(ids)}")
    # 3) dataset_competitors.json
    p = f"{D}/dataset_competitors.json"
    if os.path.exists(p):
        for c in json.load(open(p)):
            aid = str(c.get("trackId") or "")
            if aid and aid not in ids:
                ids[aid] = c.get("trackName") or aid
                meta[aid] = c.get("userRatingCount") or 0
        print(f"  +dataset_competitors: {len(ids)}")
    # 4) shard_reviews_*.json (原有评论分片输入)
    for i in (1, 2, 3, 4):
        p = f"{BASE}/采集器/inputs/shard_reviews_{i}.json"
        if os.path.exists(p):
            for x in json.load(open(p)):
                if isinstance(x, dict):
                    aid = str(x.get("app_id") or x.get("trackId") or x.get("id") or "")
                    if aid and aid not in ids:
                        ids[aid] = x.get("app_name") or x.get("trackName") or aid
                        meta[aid] = x.get("userRatingCount") or 0
                elif isinstance(x, str) and x not in ids:
                    ids[x] = x
                    meta[x] = 0
            print(f"  +shard_reviews_{i}: {len(ids)}")
    # 5) v2_bot1/v2_bot2 已采到的 app 也纳入
    for s in ("v2_bot1", "v2_bot2"):
        p = f"{D}/{s}/reviews.jsonl"
        if os.path.exists(p):
            for line in open(p, encoding="utf-8"):
                line = line.strip()
                if line:
                    r = json.loads(line)
                    aid = str(r.get("app_id"))
                    if aid and aid not in ids:
                        ids[aid] = r.get("app_name") or aid
                        meta[aid] = 0
            print(f"  +{s}: {len(ids)}")
    # 6) 已有 reviews_all.jsonl 覆盖的 app
    p = f"{OUTDIR}/reviews_all.jsonl"
    if os.path.exists(p):
        for line in open(p, encoding="utf-8"):
            line = line.strip()
            if line:
                r = json.loads(line)
                aid = str(r.get("app_id"))
                if aid and aid not in ids:
                    ids[aid] = r.get("app_name") or aid
                    meta[aid] = 0
        print(f"  +reviews_all: {len(ids)}")
    return ids, meta


def main():
    shard = "bot1"
    out = f"{OUTDIR}/{shard}_reviews.jsonl"
    min_rating = 0
    args = sys.argv[1:]
    if "--shard" in args:
        shard = args[args.index("--shard") + 1]
        out = f"{OUTDIR}/{shard}_reviews.jsonl"
    if "--out" in args:
        out = args[args.index("--out") + 1]
    if "--min_rating" in args:
        min_rating = int(args[args.index("--min_rating") + 1])
    sl_i, sl_n = 0, 1
    if "--slice" in args:
        _s = args[args.index("--slice") + 1].split("/")
        sl_i, sl_n = int(_s[0]), int(_s[1])
    os.makedirs(os.path.dirname(out), exist_ok=True)

    ids, meta = build_pool(min_rating)
    # 按评分量降序: 优先抓高产 app, 最大化总条数
    items = sorted(ids.items(), key=lambda kv: -(meta.get(kv[0]) or 0))
    if sl_n > 1:
        items = items[sl_i::sl_n]
        print(f"  分片 {sl_i+1}/{sl_n}: 取 {len(items)} 个 app", flush=True)
    print(f"待采集 App: {len(items)} 个 (min_rating={min_rating}) -> {out}", flush=True)

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
    q = queue.Queue()
    for x in items:
        q.put(x)
    stats = {"done": 0, "apps": 0, "new": 0, "zero": [], "err": 0}
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
                    stats["err"] += 1
                print(f"  [{aid}] FATAL {str(e)[:50]}", flush=True)
            with LOCK:
                stats["apps"] += 1
                stats["new"] += n
                if n == 0:
                    stats["zero"].append(name)
                stats["done"] += 1
                if stats["done"] % 20 == 0:
                    el = time.time() - t0
                    print(f"  进度 {stats['done']}/{len(items)} app, 新增 {stats['new']} 条, "
                          f"{el:.0f}s, {stats['new']/max(el,1):.1f} 条/s", flush=True)
            q.task_done()

    ts = [threading.Thread(target=worker, daemon=True) for _ in range(WORKERS)]
    for t in ts:
        t.start()
    for t in ts:
        t.join()
    fh.close()

    print(f"\n完成: {stats['apps']} app, 新增 {stats['new']} 条评论, 错误 {stats['err']}")
    print(f"零评论 app: {len(stats['zero'])}")
    json.dump({"shard": shard, "out": out, "apps": stats["apps"],
               "new_reviews": stats["new"], "errors": stats["err"],
               "zero_review_apps": stats["zero"],
               "elapsed_sec": round(time.time() - t0, 1)},
              open(f"{OUTDIR}/{shard}_collect_stats.json", "w"), ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
