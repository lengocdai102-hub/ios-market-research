"""
论坛源补采 —— 每个源独立处理，失败记录原因
支持：stackexchange(API) / bing(html) / duckduckgo(html) / hn-algolia / trustpilot / yelp / irv2 / familyrv / rvwithtito
输出：采集数据/forum_extra/forum_extra.jsonl + 来源账本
"""
import json, os, re, sys, time, gzip, urllib.request, urllib.parse, argparse
from datetime import datetime, timezone
from patchright.sync_api import sync_playwright

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36")

OUT_DIR = "/Users/maike/Desktop/iOS副业调研_2026-11-09/采集数据/forum_extra"
LEDGER = "/Users/maike/Desktop/iOS副业调研_2026-11-09/采集数据/forum_sources.md"

SE_SITES = ["stackoverflow", "apple", "webapps", "travel", "outdoors", "gaming"]
SE_TAGS = ["ios", "iphone", "app-store", "itunes", "apple-pay", "icloud",
           "xcode", "swift", "macos", "ipad", "app-store-review"]
SE_QUERIES = ["app store subscription refund", "app purchase not showing",
              "app update failed install", "app crashing after update",
              "in-app purchase receipt", "app store review rejected",
              "subscription double charged", "restore purchase missing",
              "app data lost update", "refund denied subscription"]
SE_API = "https://api.stackexchange.com/2.3/search/advanced"

RV_FORUMS = [
    ("rvwithtito", "https://www.rvwithtito.com/forums/", "rvwithtito"),
    ("familyrv", "https://familyrv.com/forums/", "familyrv"),
    ("rvforum", "https://www.rvforum.com/forums/", "rvforum"),
    ("irv2", "https://www.irv2.com/forums/", "irv2"),
]

ledger = []


def log(m):
    print(m, flush=True)


def now():
    return datetime.now(timezone.utc).isoformat()


def rec(**kw):
    kw.setdefault("collected_at", now())
    return kw


# ---------------- StackExchange ----------------
def se_fetch(opener, url):
    req = urllib.request.Request(url, headers={
        "User-Agent": UA, "Accept-Encoding": "gzip", "Accept": "application/json"})
    with opener.open(req, timeout=45) as r:
        data = r.read()
        if r.headers.get("Content-Encoding") == "gzip":
            data = gzip.decompress(data)
        return json.loads(data.decode("utf-8"))


def collect_stackexchange(fh, delay=3.5):
    """tagged + query 两种口径；直连优先，失败回退代理"""
    stats = {"ok": 0, "fail": 0, "detail": []}
    openers = [
        urllib.request.build_opener(urllib.request.ProxyHandler({})),
        urllib.request.build_opener(),
    ]
    jobs = []
    for site in SE_SITES:
        for q in SE_QUERIES:
            jobs.append(("q", site, q))
        for tg in SE_TAGS:
            jobs.append(("tag", site, tg))
    for kind, site, key in jobs:
        if kind == "q":
            params = urllib.parse.urlencode({
                "site": site, "order": "desc", "sort": "votes", "q": key,
                "pagesize": 50, "filter": "default"})
        else:
            params = urllib.parse.urlencode({
                "site": site, "order": "desc", "sort": "votes", "tagged": key,
                "pagesize": 50, "filter": "default"})
        url = f"{SE_API}?{params}"
        d = None
        err = None
        for op in openers:
            try:
                d = se_fetch(op, url)
                if "error_message" in d:
                    err = f"API {d.get('error_message')}"
                    d = None
                else:
                    break
            except Exception as e:
                err = f"{type(e).__name__}: {str(e)[:60]}"
        if d is None:
            stats["fail"] += 1
            stats["detail"].append(f"{site}/{kind}:{key} -> {err}")
            time.sleep(delay * 1.5)
            continue
        items = d.get("items", [])
        for it in items:
            fh.write(json.dumps(rec(
                source="stackexchange", site=site, query=key, query_kind=kind,
                title=it.get("title"), url=it.get("link"),
                score=it.get("score"), answers=it.get("answer_count"),
                views=it.get("view_count"), is_answered=it.get("is_answered"),
                created=it.get("creation_date"), last_activity=it.get("last_activity_date"),
                tags=it.get("tags"),
                body_snippet=re.sub(r"<[^>]+>", " ", (it.get("body") or ""))[:600],
            ), ensure_ascii=False) + "\n")
        stats["ok"] += 1
        fh.flush()
        log(f"  SE {site:13} {kind}:{key[:24]:26} {len(items):3} 条 quota={d.get('quota_remaining')}")
        time.sleep(delay)
    return stats


# ---------------- Bing HTML ----------------
def collect_bing(pg, fh, queries, pages=2):
    stats = {"ok": 0, "fail": 0, "detail": []}
    for q in queries:
        got = 0
        for p in range(1, pages + 1):
            url = (f"https://www.bing.com/search?q={urllib.parse.quote(q)}"
                   f"&first={1 + (p-1)*10}&count=30&setlang=en&cc=US&mkt=en-US")
            try:
                pg.goto(url, wait_until="domcontentloaded", timeout=40000)
                pg.wait_for_timeout(900)
                items = pg.evaluate("""() => Array.from(document.querySelectorAll('li.b_algo')).map(li=>{
                    const a=li.querySelector('h2 a'); if(!a) return null;
                    const cite=li.querySelector('.tptt, cite'); const desc=li.querySelector('.b_caption p, .b_lineclamp2');
                    const cap = li.querySelector('.b_attribution cite, cite');
                    let real = a.href;
                    const m = a.href.match(/[?&]u=a1([a-zA-Z0-9_-]+)/);
                    if (m) { try { real = decodeURIComponent(atob(m[1].replace(/-/g,'+').replace(/_/g,'/'))); } catch(e){} }
                    return {title:a.innerText.trim(), url:real, raw_url:a.href,
                            site: cap? cap.innerText.trim():(cite? cite.innerText.trim():null),
                            desc: desc? desc.innerText.trim():null};
                }).filter(Boolean)""")
            except Exception as e:
                stats["fail"] += 1
                stats["detail"].append(f"bing/{q}/p{p}: {type(e).__name__} {str(e)[:60]}")
                break
            for it in items:
                if not it.get("url"):
                    continue
                fh.write(json.dumps(rec(source="bing", query=q, page=p, **it), ensure_ascii=False) + "\n")
                got += 1
            time.sleep(1.6)
        if got:
            stats["ok"] += 1
        fh.flush()
        log(f"  bing {q[:44]:46} {got:3} 条")
    return stats


# ---------------- DuckDuckGo HTML ----------------
def collect_ddg(pg, fh, queries):
    stats = {"ok": 0, "fail": 0, "detail": []}
    for q in queries:
        got = 0
        try:
            pg.goto(f"https://html.duckduckgo.com/html/?q={urllib.parse.quote(q)}",
                    wait_until="domcontentloaded", timeout=40000)
            pg.wait_for_timeout(1200)
            items = pg.evaluate("""() => Array.from(document.querySelectorAll('.result, .web-result')).map(r=>{
                const a=r.querySelector('a.result__a'); if(!a) return null;
                const s=r.querySelector('.result__snippet');
                return {title:a.innerText.trim(), url:a.href, snippet: s? s.innerText.trim():null};
            }).filter(Boolean)""")
        except Exception as e:
            stats["fail"] += 1
            stats["detail"].append(f"ddg/{q}: {type(e).__name__} {str(e)[:60]}")
            continue
        for it in items:
            if not it.get("url"):
                continue
            fh.write(json.dumps(rec(source="duckduckgo", query=q, **it), ensure_ascii=False) + "\n")
            got += 1
        fh.flush()
        if got:
            stats["ok"] += 1
        log(f"  ddg  {q[:44]:46} {got:3} 条")
        time.sleep(2.0)
    return stats


# ---------------- HN Algolia ----------------
def collect_hn(fh, queries):
    stats = {"ok": 0, "fail": 0, "detail": []}
    for q in queries:
        got = 0
        try:
            url = f"https://hn.algolia.com/api/v1/search?query={urllib.parse.quote(q)}&tags=story&hitsPerPage=50"
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=30) as r:
                d = json.loads(r.read().decode("utf-8"))
        except Exception as e:
            stats["fail"] += 1
            stats["detail"].append(f"hn/{q}: {type(e).__name__} {str(e)[:60]}")
            continue
        for h in d.get("hits", []):
            story = h.get("story_id") or h.get("objectID")
            fh.write(json.dumps(rec(
                source="hackernews", query=q, title=h.get("title") or h.get("story_title"),
                url=h.get("url") or f"https://news.ycombinator.com/item?id={story}",
                hn_id=story, points=h.get("points"), author=h.get("author"),
                comment_text=(h.get("comment_text") or "")[:600],
                created=h.get("created_at"),
            ), ensure_ascii=False) + "\n")
            got += 1
        fh.flush()
        if got:
            stats["ok"] += 1
        log(f"  hn   {q[:44]:46} {got:3} 条")
        time.sleep(1.5)
    return stats


# ---------------- 房车论坛（浏览器） ----------------
def collect_rv_forums(pg, fh, boards):
    stats = {"ok": 0, "fail": 0, "detail": []}
    for name, url, key in boards:
        got = 0
        try:
            pg.goto(url, wait_until="domcontentloaded", timeout=40000)
            pg.wait_for_timeout(2000)
            items = pg.evaluate("""() => Array.from(document.querySelectorAll('a')).map(a=>{
                const t=(a.innerText||'').trim();
                if(!t || t.length<12) return null;
                const h=a.getAttribute('href')||'';
                if(!/thread|topic|showthread|\\/forum\\/\\d|\\/t\\//i.test(h)) return null;
                if(a.hostname && a.hostname!==location.hostname) return null;
                return {title:t.slice(0,160), url:new URL(h,location.href).href};
            }).filter(Boolean)""")
        except Exception as e:
            stats["fail"] += 1
            stats["detail"].append(f"{name}: {type(e).__name__} {str(e)[:70]}")
            log(f"  ! {name:14} {type(e).__name__} {str(e)[:60]}")
            continue
        seen = set()
        for it in items:
            if it["url"] in seen:
                continue
            seen.add(it["url"])
            fh.write(json.dumps(rec(source="rv_forum", forum=name, **it), ensure_ascii=False) + "\n")
            got += 1
        fh.flush()
        if got:
            stats["ok"] += 1
        log(f"  rv   {name:14} {got:3} 条  url={url}")
        time.sleep(2.0)
    return stats


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(OUT_DIR, "forum_extra.jsonl"))
    ap.add_argument("--only", default="")
    a = ap.parse_args()
    os.makedirs(OUT_DIR, exist_ok=True)
    only = set(a.only.split(",")) if a.only else None

    RV_QUERIES = ["RV app subscription problem", "RV navigation app offline",
                   "RV leveling app cost", "RV campground booking complaint",
                   "RV propane tank monitor app",
                   "app store subscription", "app store refund",
                   "app store review rejected", "in-app purchase problem",
                   "app data lost", "ios app crashed", "apple pay problem",
                   "app store account", "icloud sync problem",
                   "app not showing in app store", "subscription renewal charge",
                   "app store family sharing", "apple watch app problem",
                   "ipad app not updating"]
    SE_Q = SE_QUERIES

    with open(a.out, "a", encoding="utf-8") as fh:
        if only is None or "se" in only:
            log("### StackExchange ###")
            s = collect_stackexchange(fh)
            ledger.append(("stackexchange", SE_API, "200", s["ok"], len(SE_QUERIES) * len(SE_SITES), s["detail"][:5]))
        if only is None or "hn" in only:
            log("### Hacker News Algolia ###")
            s = collect_hn(fh, RV_QUERIES)
            ledger.append(("hackernews", "https://hn.algolia.com/api/v1/search", "200", s["ok"], len(RV_QUERIES), s["detail"][:5]))
        if only is None or "bing" in only or "ddg" in only or "rv" in only:
            with sync_playwright() as pw:
                b = pw.chromium.launch(channel="chrome", headless=True, args=["--no-sandbox"])
                ctx = b.new_context(user_agent=UA, locale="en-US", viewport={"width": 1440, "height": 900})
                pg = ctx.new_page()
                if only is None or "bing" in only:
                    log("### Bing ###")
                    s = collect_bing(pg, fh, RV_QUERIES, pages=2)
                    ledger.append(("bing", "https://www.bing.com/search", "200", s["ok"], len(RV_QUERIES), s["detail"][:5]))
                if only is None or "ddg" in only:
                    log("### DuckDuckGo ###")
                    s = collect_ddg(pg, fh, RV_QUERIES)
                    ledger.append(("duckduckgo", "https://html.duckduckgo.com/html/", "200", s["ok"], len(RV_QUERIES), s["detail"][:5]))
                if only is None or "rv" in only:
                    log("### RV Forums ###")
                    s = collect_rv_forums(pg, fh, RV_FORUMS)
                    ledger.append(("rv_forums", "https://www.rvwithtito.com/forums/ 等", "混合", s["ok"], len(RV_FORUMS), s["detail"][:5]))
                b.close()
    log("=== DONE ===")
    for r in ledger:
        log(f"  {r[0]:16} HTTP={r[2]:5} ok={r[3]} 条")
    json.dump(ledger, open(os.path.join(OUT_DIR, "_ledger.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
