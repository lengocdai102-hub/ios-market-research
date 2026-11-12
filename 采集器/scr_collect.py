"""
Apple App Store 采集器 —— 基于实测逆向的结构

## 实测结论（2026-11 核验）
1. see-all=reviews 页内嵌 <script type="application/json">，路径:
   data[0].data.shelfMapping.allProductReviews.items[].review
   —— 比 HTML CSS 解析可靠得多，且天然去重（HTML 里同一评论出现 2 次：弹窗版+主版）
2. 权威评分分布在 data[0].data.shelfMapping.productRatings.items[0]:
   ratingAverage / totalNumberOfRatings / ratingCounts[5..1]
   —— ratingCounts 之和 == totalNumberOfRatings，加权平均 == ratingAverage（误差<0.04）
   —— 比 HTML style="width:X%" 精确，且能自洽校验
3. 评论固定 10 条，排序是 impressionType="helpfulReview"（最有帮助），非时间序。
   所有 query 参数（sort/offset/limit）服务端一律忽略。
4. review.contents 被 Apple 截断在 ~1434-1474 字符。
5. 评分量=0 的 App 页面 302，无评论 —— 数据事实，不是失败。
"""
import json, re, os, sys, time, argparse, urllib.request, urllib.parse
from datetime import datetime

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")
OUT = os.environ.get("SCR_OUT", "/tmp/scr_out")
BASE_APP = "https://apps.apple.com/us/app/id{}"
LOOKUP = "https://itunes.apple.com/lookup?id={}&country=us"

GENRES = {"6014": "Business", "6016": "Navigation", "6012": "Lifestyle",
          "6027": "Health-Fitness", "6020": "Travel", "6008": "Finance",
          "6024": "Medical", "6007": "Productivity", "6006": "Education",
          "6018": "Sports", "6022": "Games", "6023": "News",
          "6026": "Entertainment", "6005": "Social-Networking", "6038": "Food-Drink",
          "6011": "Shopping", "6029": "Utilities", "6015": "Weather",
          "6031": "Reference", "6003": "Music", "6021": "Books",
          "6002": "Photography", "6010": "Magazines", "6017": "Entertainment"}


def log(m):
    print(m, flush=True)


def get(url, tries=3):
    last = None
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "en-US,en;q=0.9"})
            with urllib.request.urlopen(req, timeout=45) as r:
                return r.read().decode("utf-8", "ignore")
        except Exception as e:
            last = e
            time.sleep(1.5 * (i + 1))
    raise last


# ---------------- JSON 解析 ----------------

def extract_blob(html):
    """取页面内嵌的 application/json 数据块"""
    m = re.search(r'<script[^>]*type="application/json"[^>]*>(.*?)</script>', html, re.S)
    if not m:
        return None
    try:
        return json.loads(m.group(1))
    except Exception:
        return None


def parse_reviews_json(html):
    """从内嵌 JSON 解析评论 + 权威评分分布。返回 (reviews, ratings_dict)"""
    blob = extract_blob(html)
    if not blob:
        return [], {}
    try:
        dd = blob["data"][0]["data"]
    except Exception:
        return [], {}

    reviews = []
    shelf = dd.get("shelfMapping", {}).get("allProductReviews", {})
    for it in shelf.get("items", []) or []:
        rv = it.get("review") or {}
        if not rv.get("id"):
            continue
        reviews.append({
            "review_id": rv.get("id"),
            "stars": rv.get("rating"),
            "date": (rv.get("date") or "")[:10],
            "title": (rv.get("title") or "").strip(),
            "body": (rv.get("contents") or "").strip(),
            "author": (rv.get("reviewerName") or "").strip(),
            "sort_type": ((it.get("impressionMetrics") or {}).get("fields") or {}).get("impressionType", ""),
            "developer_response": bool(rv.get("response")),
        })

    ratings = {}
    try:
        pr = dd["shelfMapping"]["productRatings"]["items"][0]
        counts = pr.get("ratingCounts") or []
        total = pr.get("totalNumberOfRatings")
        avg = pr.get("ratingAverage")
        if counts and total:
            ratings = {
                "avg_rating": avg,
                "rating_count": int(total),
                "counts_5_to_1": [int(round(c)) for c in counts],
                "dist_pct": {str(5 - i): round(c / total * 100, 2) for i, c in enumerate(counts)},
            }
            # 自洽校验
            s = sum(ratings["counts_5_to_1"])
            ratings["counts_sum"] = s
            ratings["self_consistent"] = (s == int(total))
            w = sum((5 - i) * c for i, c in enumerate(ratings["counts_5_to_1"])) / s if s else 0
            ratings["weighted_avg"] = round(w, 3)
            ratings["avg_delta"] = round(abs(w - avg), 3) if avg else None
    except Exception:
        pass
    return reviews, ratings


def parse_reviews(html):
    """兼容入口：返回 (reviews, ratings)"""
    return parse_reviews_json(html)


# ---------------- 采集子命令 ----------------

def cmd_reviews(args):
    ids = norm_ids(load_json(args.ids))
    os.makedirs(OUT, exist_ok=True)
    fr = open(f"{OUT}/reviews.jsonl", "a")
    meta_map = {}
    if os.path.exists(f"{OUT}/review_targets_meta.json"):
        try:
            meta_map = {str(x["app_id"]): x for x in json.load(open(f"{OUT}/review_targets_meta.json"))}
        except Exception:
            meta_map = {}
    for aid in ids:
        aid = str(aid)
        try:
            html = get(f"{BASE_APP.format(aid)}?see-all=reviews")
            rvs, ratings = parse_reviews_json(html)
            name = ""
            m = re.search(r"<title>(.*?)</title>", html, re.S)
            if m:
                name = re.sub(r"^[^A-Za-z0-9\u4e00-\u9fff\u3000-\u30ff]+", "", m.group(1)).strip()
                name = re.sub(r"\s*-\s*(Ratings.*|App Store.*)$", "", name).strip()
            meta = dict(meta_map.get(aid, {}))
            meta.update({"app_id": aid, "app_name": name})
            meta.update({k: v for k, v in ratings.items() if k != "dist_pct"})
            if ratings.get("dist_pct"):
                meta["rating_dist_pct"] = ratings["dist_pct"]
            meta_map[aid] = meta
            for r in rvs:
                r["app_id"] = aid
                r["app_name"] = name
                fr.write(json.dumps(r, ensure_ascii=False) + "\n")
            fr.flush()
            log(f"[评论] {name[:38]:40} {len(rvs):>2}条  总评分数={ratings.get('rating_count')}  分布={ratings.get('dist_pct')}")
        except Exception as e:
            log(f"[评论] {aid} 失败: {str(e)[:80]}")
        time.sleep(args.delay)
    fr.close()
    json.dump(list(meta_map.values()), open(f"{OUT}/review_targets_meta.json", "w"), ensure_ascii=False, indent=2)
    log(f"[评论] meta -> {OUT}/review_targets_meta.json  ({len(meta_map)} 个 app)")


def cmd_lookup(args):
    ids = norm_ids(load_json(args.ids))
    os.makedirs(OUT, exist_ok=True)
    fl = open(f"{OUT}/competitors.jsonl", "a")
    for aid in ids:
        aid = str(aid)
        try:
            j = json.loads(get(LOOKUP.format(aid)))
            res = j.get("results") or []
            if not res:
                log(f"[详情] {aid} lookup 无结果")
                continue
            r = res[0]
            row = {
                "app_id": aid,
                "app_name": r.get("trackName"),
                "seller": r.get("sellerName"),
                "genre": r.get("primaryGenreName"),
                "genres": r.get("genres"),
                "price": r.get("price"),
                "currency": r.get("currency"),
                "formatted_price": r.get("formattedPrice"),
                "avg_rating": r.get("averageUserRating"),
                "rating_count": r.get("userRatingCount"),
                "version": r.get("version"),
                "current_version_release": (r.get("currentVersionReleaseDate") or "")[:10],
                "first_release": (r.get("releaseDate") or "")[:10],
                "size_bytes": r.get("fileSizeBytes"),
                "size_mb": round(r.get("fileSizeBytes", 0) / 1048576, 1) if r.get("fileSizeBytes") else None,
                "min_os": r.get("minimumOsVersion"),
                "content_rating": r.get("trackContentRating"),
                "advisories": r.get("advisories"),
                "genres_ids": r.get("genreIds"),
            }
            fl.write(json.dumps(row, ensure_ascii=False) + "\n")
            fl.flush()
            log(f"[详情] {str(r.get('trackName'))[:38]:40} 评分数={r.get('userRatingCount')} 价={r.get('formattedPrice')}")
        except Exception as e:
            log(f"[详情] {aid} 失败: {str(e)[:70]}")
        time.sleep(args.delay)
    fl.close()


def cmd_charts(args):
    os.makedirs(OUT, exist_ok=True)
    fc = open(f"{OUT}/charts.jsonl", "a")
    types = ["topfreeapplications", "toppaidapplications", "topgrossingapplications"]
    if args.genres:
        gids = [g.strip() for g in args.genres.split(",") if g.strip()]
    elif args.all_genres:
        gids = list(GENRES.keys())
    else:
        gids = ["6014"]
    for t in types:
        for g in gids:
            url = f"https://itunes.apple.com/us/rss/{t}/limit=100/genre={g}/json"
            try:
                j = json.loads(get(url))
                feed = j.get("feed") or {}
                for e in (feed.get("entry") or []):
                    idu = (e.get("id") or {}).get("attributes", {}).get("im:id") or ""
                    aid = re.sub(r"\D", "", idu)
                    row = {
                        "chart": t, "chart_name": {"topfreeapplications": "免费榜",
                                                  "toppaidapplications": "付费榜",
                                                  "topgrossingapplications": "畅销榜"}[t],
                        "genre_id": g, "genre_name": GENRES.get(g, g),
                        "rank": int((e.get("attributes") or {}).get("im:rank", 0) or 0),
                        "app_id": aid,
                        "app_name": ((e.get("title") or {}).get("label") if isinstance(e.get("title"), dict) else e.get("title")),
                        "seller": e.get("author", {}).get("name", "") if isinstance(e.get("author"), dict) else "",
                        "url": (e.get("id") or {}).get("label", ""),
                        "price": ((e.get("attributes") or {}).get("price") or {}) if isinstance((e.get("attributes") or {}).get("price"), dict) else None,
                    }
                    fc.write(json.dumps(row, ensure_ascii=False) + "\n")
                fc.flush()
                log(f"[榜单] {t:26} {GENRES.get(g,g):14} {(feed.get('entry') or []) and len(feed.get('entry')) or 0} 条")
            except Exception as e:
                log(f"[榜单] {t}/{g} 失败: {str(e)[:60]}")
            time.sleep(args.delay)
    fc.close()


def cmd_community(args):
    """Apple 社区提问 —— 需真实 Chrome 渲染 (Cloudflare)"""
    os.makedirs(OUT, exist_ok=True)
    from patchright.sync_api import sync_playwright
    queries = load_json(args.queries)
    ft = open(f"{OUT}/community_threads.jsonl", "a")
    with sync_playwright() as p:
        br = p.chromium.launch(channel="chrome", headless=True)
        pg = br.new_page(user_agent=UA, locale="en-US")
        for q in queries:
            try:
                pg.goto(f"https://discussions.apple.com/search?q={urllib.parse.quote(q)}",
                        wait_until="domcontentloaded", timeout=60000)
                pg.wait_for_timeout(3500)
                seen = set()
                for el in pg.query_selector_all("a.thread-title[href*='/thread/']"):
                    href = el.get_attribute("href") or ""
                    if not href or href in seen:
                        continue
                    seen.add(href)
                    try:
                        title = (el.inner_text() or "").strip().replace("\n", " ")
                    except Exception:
                        title = ""
                    if not title:
                        continue
                    ft.write(json.dumps({
                        "query": q, "title": title,
                        "url": "https://discussions.apple.com" + href if href.startswith("/") else href,
                        "thread_id": href.rsplit("/", 1)[-1],
                        "collected_at": datetime.now().isoformat(timespec="seconds"),
                    }, ensure_ascii=False) + "\n")
                ft.flush()
                log(f"[社区] '{q[:32]}' -> {len(seen)} 帖")
            except Exception as e:
                log(f"[社区] '{q[:32]}' 失败: {str(e)[:70]}")
            time.sleep(args.delay)
        br.close()
    ft.close()


def load_json(p):
    if not p or p == "-":
        return json.load(sys.stdin)
    with open(p) as f:
        return json.load(f)


def norm_ids(raw):
    """输入可能是 [id,...] 或 [{trackId:...},...] 或 [{app_id:...},...]"""
    out = []
    for x in raw:
        if isinstance(x, (int, str)):
            out.append(str(x))
        elif isinstance(x, dict):
            for k in ("trackId", "app_id", "id", "track_id"):
                if k in x:
                    out.append(str(x[k]))
                    break
    return out


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("reviews"); c.add_argument("--ids", required=True); c.add_argument("--delay", type=float, default=1.0)
    c = sub.add_parser("lookup"); c.add_argument("--ids", required=True); c.add_argument("--delay", type=float, default=0.5)
    c = sub.add_parser("charts"); c.add_argument("--all_genres", action="store_true"); c.add_argument("--genres"); c.add_argument("--delay", type=float, default=0.8)
    c = sub.add_parser("community"); c.add_argument("--queries", required=True); c.add_argument("--delay", type=float, default=2.0)
    args = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)
    {"reviews": cmd_reviews, "lookup": cmd_lookup, "charts": cmd_charts, "community": cmd_community}[args.cmd](args)


if __name__ == "__main__":
    main()
