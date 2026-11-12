#!/usr/bin/env python3
"""
采集 App Store 商品页权威评分分布 ratingCounts / totalNumberOfRatings / ratingAverage。

解析路径 (已实测):
  <script type="application/json"> -> data[0].data.shelfMapping.productRatings.items[0]
  -> ratingCounts[5,4,3,2,1], totalNumberOfRatings, ratingAverage

实测: urllib 直连 apps.apple.com 可用 (不需要 Scrapling/代理), Outdoorsy(1443835927)
      ratingCounts=[19838,1646,307,94,428] total=22313 avg=4.8 与官方一致。

用法: scr_rating_counts.py [--limit N] [--delay S] [--out PATH]
断点续跑: 已存在的 app_id 跳过。失败也写一行 (http_status 非 200)。
"""
import json, os, re, sys, time, urllib.request, urllib.error

BASE = "/Users/maike/Desktop/iOS副业调研_2026-11-09"
D = f"{BASE}/采集数据"
OUT = f"{D}/rating_counts.jsonl"
TARGETS = f"{D}/rating_targets.json"
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")

BLOB_RE = re.compile(r'<script[^>]*type="application/json"[^>]*>(.*?)</script>', re.S)


def get(url, tries=3, timeout=45):
    last = None
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={
                "User-Agent": UA,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9",
            })
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.status, r.read().decode("utf-8", "ignore")
        except urllib.error.HTTPError as e:
            return e.code, ""
        except Exception as e:
            last = e
            time.sleep(1.0 * (i + 1))
    raise last


def parse_ratings(html):
    """从内嵌 JSON 提取 ratingCounts / total / avg。
    返回 (counts5to1, total, avg, avg_from_counts, err)"""
    m = BLOB_RE.search(html)
    if not m:
        return None, None, None, None, "no_json_blob"
    try:
        blob = json.loads(m.group(1))
    except Exception as e:
        return None, None, None, None, f"json_parse_fail:{str(e)[:40]}"
    # 路径 1: shelfMapping.productRatings.items[0]
    # 注意: 零评分 app 也有 ratingCounts=[0,0,0,0,0] total=0, 属有效数据(非失败)
    try:
        pr = blob["data"][0]["data"]["shelfMapping"]["productRatings"]["items"][0]
        counts = pr.get("ratingCounts") or []
        total = pr.get("totalNumberOfRatings")
        avg = pr.get("ratingAverage")
        if counts and total is not None:
            return [int(round(c)) for c in counts], int(total), avg, None, None
    except Exception:
        pass
    # 路径 2: 全量递归搜 ratingCounts
    found = []

    def walk(o):
        if isinstance(o, dict):
            if "ratingCounts" in o and "totalNumberOfRatings" in o:
                found.append(o)
            for v in o.values():
                walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)

    walk(blob)
    if found:
        o = found[0]
        counts = o.get("ratingCounts") or []
        total = o.get("totalNumberOfRatings")
        avg = o.get("ratingAverage")
        if counts and total is not None:
            return [int(round(c)) for c in counts], int(total), avg, None, None
    return None, None, None, None, "no_ratingcounts_field"


def main():
    limit = 0
    delay = 0.6
    out = OUT
    args = sys.argv[1:]
    if "--limit" in args:
        limit = int(args[args.index("--limit") + 1])
    if "--delay" in args:
        delay = float(args[args.index("--delay") + 1])
    if "--out" in args:
        out = args[args.index("--out") + 1]

    targets = json.load(open(TARGETS))
    if limit:
        targets = targets[:limit]

    done = set()
    if os.path.exists(out):
        for line in open(out, encoding="utf-8"):
            line = line.strip()
            if line:
                try:
                    done.add(str(json.loads(line).get("app_id")))
                except Exception:
                    pass
    todo = [t for t in targets if str(t["app_id"]) not in done]
    print(f"总目标 {len(targets)}, 已完成 {len(done)}, 待采 {len(todo)}", flush=True)

    ok = fail = 0
    sum_ok = 0
    avg_ok = 0
    avg_ok_strict = 0
    zero_n = 0
    t0 = time.time()
    with open(out, "a", encoding="utf-8") as fh:
        for i, t in enumerate(todo, 1):
            aid = str(t["app_id"])
            url = f"https://apps.apple.com/us/app/id{aid}"
            rec = {"app_id": aid, "app_name": t.get("app_name"),
                   "fetched_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "url": url}
            try:
                status, html = get(url)
                rec["http_status"] = status
                if status != 200:
                    rec.update({"ratingCounts": None, "total": None, "rating_avg": None,
                                "fetch_status": "FAIL", "error": f"http_{status}"})
                    fail += 1
                else:
                    counts, total, avg, _, err = parse_ratings(html)
                    if not counts:
                        rec.update({"ratingCounts": None, "total": None, "rating_avg": None,
                                    "fetch_status": "FAIL", "error": err or "parse_fail"})
                        fail += 1
                    else:
                        d = {"1": counts[4], "2": counts[3], "3": counts[2],
                             "4": counts[1], "5": counts[0]}
                        cs = sum(counts)
                        rec["ratingCounts"] = d
                        rec["total"] = total
                        rec["rating_avg"] = avg
                        rec["ratingCounts_sum"] = cs
                        rec["sum_matches_total"] = (cs == total)
                        if total:
                            wavg = sum((5 - idx) * c for idx, c in enumerate(counts)) / cs if cs else 0
                            rec["rating_avg_from_counts"] = round(wavg, 4)
                            try:
                                a = float(avg)
                                rec["avg_diff"] = round(abs(a - wavg), 4)
                                # Apple 页面的 ratingAverage 只保留 1 位小数,
                                # 故主口径 = 舍入到 1 位后比较 (|差|<0.05),
                                # 原始差另存 avg_diff 供审阅
                                rec["avg_diff_rounded"] = round(abs(a - round(wavg, 1)), 4)
                                rec["avg_consistent"] = rec["avg_diff_rounded"] < 0.05
                                rec["avg_consistent_strict"] = rec["avg_diff"] < 0.02
                                avg_ok += 1 if rec["avg_consistent"] else 0
                                avg_ok_strict += 1 if rec["avg_consistent_strict"] else 0
                            except Exception:
                                rec["avg_consistent"] = None
                            rec["fetch_status"] = "ok"
                            ok += 1
                            sum_ok += 1 if rec.get("sum_matches_total") else 0
                        else:
                            # 零评分 app: 数据有效但无评分分布, 单列统计
                            rec["fetch_status"] = "ok"
                            rec["zero_rating"] = True
                            rec["rating_avg_from_counts"] = None
                            rec["avg_consistent"] = None
                            ok += 1
                            zero_n += 1
                            sum_ok += 1 if rec.get("sum_matches_total") else 0
            except Exception as e:
                rec.update({"http_status": 0, "ratingCounts": None, "total": None,
                            "rating_avg": None, "fetch_status": "FAIL",
                            "error": str(e)[:80]})
                fail += 1
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
            fh.flush()
            if i % 25 == 0:
                el = time.time() - t0
                print(f"  进度 {i}/{len(todo)}  ok={ok} fail={fail} "
                      f"{el:.0f}s ({i/max(el,1):.1f}/s)", flush=True)
            time.sleep(delay)

    print(f"完成: ok={ok} fail={fail} (其中零评分 app {zero_n}) | "
          f"sum==total 通过 {sum_ok}/{ok} | "
          f"平均分自洽(1位小数口径,<0.05) {avg_ok}/{max(ok-zero_n,1)} | "
          f"(严格<0.02) {avg_ok_strict}/{max(ok-zero_n,1)} | 用时 {time.time()-t0:.0f}s")
    print(f"-> {out}")


if __name__ == "__main__":
    main()
