"""
论坛 / UGC / 社区 数据采集器
实测可用源（2026-11 核验）:
  ✔ Google News RSS      https://news.google.com/rss/search?q=...&hl=en-US&gl=US&ceid=US:en
  ✔ GitHub API           api.github.com/search/issues  (开发者真实抱怨)
  ✔ StackExchange API    api.stackexchange.com/2.3  (site=travel|gaming|webapps|stackoverflow)
  ✔ HN Algolia API       hn.algolia.com/api/v1  (开发者/产品讨论)
  ✔ Bing News RSS        www.bing.com/news/search?q=...&format=RSS  (条数少, 备用)
  ✔ old.reddit  → 登录墙, 不可用
  ✘ Reddit JSON/RSS     403/429, 需登录验证
  ✘ 房车论坛 (RVforum/iRV2/Motorhome/TravelTrails)  Cloudflare 挑战
  ✘ Quora                403
"""
import json, os, re, sys, time, argparse, urllib.request, urllib.parse, html as htmlmod
from datetime import datetime

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")
OUT = os.environ.get("SCR_OUT", "/tmp/scr_out")
NOW = datetime.now().isoformat(timespec="seconds")


def log(m):
    print(m, flush=True)


def get(url, tries=3, hdr=None):
    h = {"User-Agent": UA, "Accept-Language": "en-US,en;q=0.9"}
    if hdr: h.update(hdr)
    last = None
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers=h)
            with urllib.request.urlopen(req, timeout=40) as r:
                return r.read().decode("utf-8", "ignore")
        except urllib.error.HTTPError as e:
            last = e
            if e.code == 429:          # 限流: 退避到 20s 再试
                wait = 20 * (i + 1)
                log(f"  [429 限流] 等待 {wait}s 后重试")
                time.sleep(wait)
                continue
            time.sleep(1.2 * (i + 1))
        except Exception as e:
            last = e
            time.sleep(1.2 * (i + 1))
    raise last


def strip_tags(s):
    s = re.sub(r"<[^>]+>", " ", s or "")
    s = htmlmod.unescape(s)
    return re.sub(r"\s+", " ", s).strip()


# ---------- Google News RSS ----------
def cmd_gnews(args):
    queries = load_json(args.queries)
    os.makedirs(OUT, exist_ok=True)
    f = open(f"{OUT}/gnews.jsonl", "a")
    for q in queries:
        try:
            url = (f"https://news.google.com/rss/search?q={urllib.parse.quote(q)}"
                   f"&hl=en-US&gl=US&ceid=US:en")
            h = get(url)
            items = re.findall(r"<item>(.*?)</item>", h, re.S)
            n = 0
            for it in items:
                def g(tag):
                    m = re.search(rf"<{tag}[^>]*>(.*?)</{tag}>", it, re.S)
                    return strip_tags(m.group(1)) if m else ""
                src = re.search(r"<source[^>]*>(.*?)</source>", it, re.S)
                row = {
                    "source_type": "gnews", "query": q,
                    "title": g("title"), "link": g("link"),
                    "published": g("pubDate"),
                    "publisher": strip_tags(src.group(1)) if src else "",
                    "snippet": g("description")[:600],
                    "collected_at": NOW,
                }
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
                n += 1
            f.flush()
            log(f"[GNews] '{q[:40]}' -> {n} 条")
        except Exception as e:
            log(f"[GNews] '{q[:40]}' 失败: {str(e)[:70]}")
        time.sleep(args.delay)
    f.close()


# ---------- StackExchange ----------
def cmd_stackexchange(args):
    """按 tag 检索 (比全文 query 命中率高) + 可选全文查询"""
    sites = [s.strip() for s in args.sites.split(",")]
    os.makedirs(OUT, exist_ok=True)
    f = open(f"{OUT}/stackexchange.jsonl", "a")
    seen = set()
    # 1) tag 模式
    for site in sites:
        for tag in args.tags:
            try:
                url = ("https://api.stackexchange.com/2.3/questions?"
                       f"site={site}&tagged={urllib.parse.quote(tag)}"
                       f"&pagesize={args.limit}&order=desc&sort=votes&filter=withbody")
                j = json.loads(get(url))
                n = 0
                for it in j.get("items", []):
                    qid = it.get("question_id")
                    if qid in seen: continue
                    seen.add(qid)
                    row = {
                        "source_type": "stackexchange", "site": site, "query": f"tag:{tag}",
                        "question_id": qid, "title": it.get("title"),
                        "score": it.get("score"), "answer_count": it.get("answer_count"),
                        "view_count": it.get("view_count"), "tags": it.get("tags"),
                        "created": (datetime.utcfromtimestamp(it["creation_date"]).strftime("%Y-%m-%d")
                                    if it.get("creation_date") else None),
                        "body": strip_tags(it.get("body"))[:1500],
                        "link": it.get("link"), "collected_at": NOW,
                    }
                    f.write(json.dumps(row, ensure_ascii=False) + "\n")
                    n += 1
                f.flush()
                log(f"[SE/tag] {site:14} {tag[:24]:26} -> {n} 条")
            except Exception as e:
                log(f"[SE/tag] {site:14} {tag[:24]:24} 失败: {str(e)[:55]}")
            time.sleep(args.delay)
    # 2) 全文 query 模式
    queries = load_json(args.queries) if args.queries else []
    for site in sites:
        for q in queries:
            try:
                url = ("https://api.stackexchange.com/2.3/search/advanced?"
                       f"order=desc&sort=votes&q={urllib.parse.quote(q)}"
                       f"&site={site}&pagesize={args.limit}&filter=withbody")
                j = json.loads(get(url))
                n = 0
                for it in j.get("items", []):
                    qid = it.get("question_id")
                    if qid in seen: continue
                    seen.add(qid)
                    row = {
                        "source_type": "stackexchange", "site": site, "query": q,
                        "question_id": qid, "title": it.get("title"),
                        "score": it.get("score"), "answer_count": it.get("answer_count"),
                        "view_count": it.get("view_count"), "tags": it.get("tags"),
                        "created": (datetime.utcfromtimestamp(it["creation_date"]).strftime("%Y-%m-%d")
                                    if it.get("creation_date") else None),
                        "body": strip_tags(it.get("body"))[:1500],
                        "link": it.get("link"), "collected_at": NOW,
                    }
                    f.write(json.dumps(row, ensure_ascii=False) + "\n")
                    n += 1
                f.flush()
                log(f"[SE/q] {site:14} '{q[:24]}' -> {n} 条")
            except Exception as e:
                log(f"[SE/q] {site:14} '{q[:24]}' 失败: {str(e)[:55]}")
            time.sleep(args.delay)
    f.close()


# ---------- Hacker News (Algolia) ----------
def cmd_hn(args):
    queries = load_json(args.queries)
    os.makedirs(OUT, exist_ok=True)
    f = open(f"{OUT}/hn.jsonl", "a")
    for q in queries:
        for by in ("search", "search_by_date"):
            try:
                url = (f"https://hn.algolia.com/api/v1/{by}?"
                       f"query={urllib.parse.quote(q)}&tags=story&hitsPerPage={args.limit}")
                j = json.loads(get(url))
                n = 0
                for h in j.get("hits", []):
                    row = {
                        "source_type": "hackernews", "query": q, "sort": by,
                        "object_id": h.get("objectID"),
                        "title": h.get("title"),
                        "points": h.get("points"),
                        "num_comments": h.get("num_comments"),
                        "created_at": h.get("created_at"),
                        "url": h.get("url"),
                        "hn_url": f"https://news.ycombinator.com/item?id={h.get('objectID')}",
                        "snippet": (h.get("story_text") or "")[:600],
                        "collected_at": NOW,
                    }
                    f.write(json.dumps(row, ensure_ascii=False) + "\n")
                    n += 1
                f.flush()
                log(f"[HN/{by}] '{q[:34]}' -> {n} 条")
            except Exception as e:
                log(f"[HN/{by}] '{q[:34]}' 失败: {str(e)[:60]}")
            time.sleep(args.delay)
    f.close()


# ---------- GitHub ----------
def cmd_github(args):
    queries = load_json(args.queries)
    os.makedirs(OUT, exist_ok=True)
    f = open(f"{OUT}/github.jsonl", "a")
    for q in queries:
        try:
            url = ("https://api.github.com/search/issues?q=" + urllib.parse.quote(q) +
                   f"&sort=created&order=desc&per_page={args.limit}")
            j = json.loads(get(url, hdr={"Accept": "application/vnd.github+json"}))
            n = 0
            for it in j.get("items", []):
                row = {
                    "source_type": "github", "query": q,
                    "repo": (it.get("repository_url") or "").rsplit("/", 1)[-1],
                    "title": it.get("title"),
                    "state": it.get("state"),
                    "comments": it.get("comments"),
                    "created_at": (it.get("created_at") or "")[:10],
                    "body": strip_tags(it.get("body"))[:1200],
                    "url": it.get("html_url"),
                    "collected_at": NOW,
                }
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
                n += 1
            f.flush()
            log(f"[GitHub] '{q[:38]}' -> {n} 条 (total={j.get('total_count')})")
        except Exception as e:
            log(f"[GitHub] '{q[:38]}' 失败: {str(e)[:70]}")
        time.sleep(args.delay)
    f.close()


def load_json(p):
    if not p or p == "-":
        return json.load(sys.stdin)
    with open(p) as f:
        return json.load(f)


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("gnews");     c.add_argument("--queries", required=True); c.add_argument("--delay", type=float, default=1.0)
    c = sub.add_parser("stackexchange"); c.add_argument("--queries"); c.add_argument("--tags", default="ios,app-store,in-app-purchase,swiftui,subscription,itunes,apple,xcode"); c.add_argument("--sites", default="stackoverflow,webapps,gaming,travel"); c.add_argument("--limit", type=int, default=30); c.add_argument("--delay", type=float, default=1.0)
    c = sub.add_parser("hn");        c.add_argument("--queries", required=True); c.add_argument("--limit", type=int, default=30); c.add_argument("--delay", type=float, default=1.0)
    c = sub.add_parser("github");    c.add_argument("--queries", required=True); c.add_argument("--limit", type=int, default=30); c.add_argument("--delay", type=float, default=1.2)
    args = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)
    {"gnews": cmd_gnews, "stackexchange": cmd_stackexchange,
     "hn": cmd_hn, "github": cmd_github}[args.cmd](args)


if __name__ == "__main__":
    main()
