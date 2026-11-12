#!/usr/bin/env python3
"""
v3 评论采集结果验证:
1) 总条数 / 覆盖 app 数 / 每 app 条数分布(中位/最大/零评论 app 数)
2) 去重校验: review_id 唯一数 == 总条数
3) 抽样验证 5 个 app: 正文非空率 / 日期跨度 / 星级分布, 并与网页权威 ratingCounts 对比
"""
import json, os, re, sys, urllib.request, collections, statistics

BASE = "/Users/maike/Desktop/iOS副业调研_2026-11-09"
D = f"{BASE}/采集数据"
OUT = f"{D}/v3_reviews"
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")

FILES = [f"{OUT}/reviews_all.jsonl", f"{OUT}/bot1_reviews.jsonl"]


def get(u, tries=3):
    last = None
    for i in range(tries):
        try:
            return urllib.request.urlopen(
                urllib.request.Request(u, headers={"User-Agent": UA}), timeout=45
            ).read().decode("utf-8", "ignore")
        except Exception as e:
            last = e
    raise last


def web_rating_counts(app_id):
    """从 apps.apple.com 页面拿权威 ratingCounts (5->1) 与总评分数"""
    h = get(f"https://apps.apple.com/us/app/id{app_id}")
    m = re.search(r'<script[^>]*type="application/json"[^>]*>(.*?)</script>', h, re.S)
    if not m:
        return None
    dd = json.loads(m.group(1))["data"][0]["data"]
    for k, v in dd.items():
        if isinstance(v, dict) and "ratingCounts" in v:
            return v["ratingCounts"], v.get("ratingCountList"), v.get("ratingValueList")
    return None


def load_all():
    rows = []
    for p in FILES:
        if os.path.exists(p):
            for line in open(p, encoding="utf-8"):
                line = line.strip()
                if line:
                    try:
                        rows.append(json.loads(line))
                    except Exception:
                        pass
    return rows


def main():
    rows = load_all()
    total = len(rows)
    ids = [r.get("review_id") for r in rows]
    uniq = len(set(ids))
    by_app = collections.Counter(r.get("app_id") for r in rows)
    counts = sorted(by_app.values())

    rep = {
        "generated_at": "2026-11-10T21:30:00+08:00",
        "sources": [p for p in FILES if os.path.exists(p)],
        "overall": {
            "total_reviews": total,
            "unique_review_ids": uniq,
            "duplicate_rows": total - uniq,
            "dedup_ok": total == uniq,
            "apps_covered": len(by_app),
            "per_app_median": int(statistics.median(counts)) if counts else 0,
            "per_app_max": max(counts) if counts else 0,
            "per_app_min": min(counts) if counts else 0,
            "per_app_mean": round(sum(counts) / len(counts), 1) if counts else 0,
        },
        "per_app_distribution": {},
    }
    buckets = [(1, 1), (2, 10), (11, 50), (51, 100), (101, 300),
               (301, 600), (601, 1000), (1001, 999999)]
    for lo, hi in buckets:
        n = sum(1 for v in counts if lo <= v <= hi)
        rep["per_app_distribution"][f"{lo}-{hi}"] = n

    # 每 app 明细(按条数降序)
    app_detail = []
    for aid, n in by_app.most_common():
        rs = [r for r in rows if r.get("app_id") == aid]
        app_detail.append({
            "app_id": aid,
            "app_name": rs[0].get("app_name"),
            "count": n,
            "unique_ids": len({r.get("review_id") for r in rs}),
            "date_min": min(r.get("date", "") for r in rs),
            "date_max": max(r.get("date", "") for r in rs),
        })
    rep["per_app"] = app_detail

    # ---- 抽样验证 5 个 app ----
    sample_ids = [x["app_id"] for x in app_detail[:3]] + \
                 [x["app_id"] for x in app_detail[len(app_detail) // 2: len(app_detail) // 2 + 1]] + \
                 [x["app_id"] for x in app_detail[-1:]]
    samples = []
    for aid in sample_ids:
        rs = [r for r in rows if r.get("app_id") == aid]
        nonempty = sum(1 for r in rs if (r.get("body") or "").strip())
        star = collections.Counter(r.get("stars") for r in rs)
        s = {
            "app_id": aid,
            "app_name": rs[0].get("app_name") if rs else None,
            "sample_n": len(rs),
            "body_nonempty_rate": round(nonempty / len(rs), 4) if rs else 0,
            "body_empty_n": len(rs) - nonempty,
            "date_min": min(r.get("date", "") for r in rs),
            "date_max": max(r.get("date", "") for r in rs),
            "year_span": sorted({r.get("date", "")[:4] for r in rs}),
            "sample_star_distribution": {str(k): v for k, v in sorted(star.items())},
            "sample_low_star_rate": round(
                (star.get(1, 0) + star.get(2, 0)) / len(rs), 4) if rs else 0,
        }
        try:
            wc = web_rating_counts(aid)
            if wc:
                counts5, cl, vl = wc
                tot = sum(counts5) if counts5 else 0
                s["web_ratingCounts"] = counts5
                s["web_total_ratings"] = tot
                s["web_low_star_rate"] = round(
                    (counts5[3] + counts5[4]) / tot, 4) if tot else None
                s["sample_vs_web_low_star_delta_pp"] = (
                    round((s["sample_low_star_rate"] - s["web_low_star_rate"]) * 100, 2)
                    if s["web_low_star_rate"] is not None else None)
                # 星级占比对比
                s["web_star_distribution"] = {
                    str(5 - i): round(c / tot, 4) for i, c in enumerate(counts5)} if tot else {}
                s["sample_star_distribution_pct"] = {
                    str(k): round(v / len(rs), 4) for k, v in sorted(star.items())} if rs else {}
        except Exception as e:
            s["web_ratingCounts_error"] = str(e)[:80]
        samples.append(s)
    rep["sample_validation"] = samples

    json.dump(rep, open(f"{OUT}/bot1_collection_report.json", "w"),
              ensure_ascii=False, indent=2)

    print("=== 总量 ===")
    print(f"  总条数        : {total}")
    print(f"  唯一 review_id: {uniq}   重复行: {total-uniq}   去重通过: {total==uniq}")
    print(f"  覆盖 app 数   : {len(by_app)}")
    print(f"  每 app 条数   : 中位 {rep['overall']['per_app_median']} / 最大 {rep['overall']['per_app_max']} / 均值 {rep['overall']['per_app_mean']}")
    print("=== 分布 ===")
    for k, v in rep["per_app_distribution"].items():
        print(f"  {k}: {v}")
    print("=== 抽样验证 ===")
    for s in samples:
        print(f"  [{s['app_name']}] n={s['sample_n']} 正文非空率={s['body_nonempty_rate']:.1%} "
              f"日期 {s['date_min']}~{s['date_max']} 年份={s['year_span']}")
        print(f"      样本低星率={s['sample_low_star_rate']:.2%} "
              f"网页低星率={s.get('web_low_star_rate')} "
              f"偏差={s.get('sample_vs_web_low_star_delta_pp')}pp")
        print(f"      样本星级={s['sample_star_distribution_pct']}")
        print(f"      网页星级={s.get('web_star_distribution')}")
    print(f"\n-> {OUT}/bot1_collection_report.json")


if __name__ == "__main__":
    main()
