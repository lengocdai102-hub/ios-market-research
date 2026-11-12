"""
论坛源补采 v2
- DuckDuckGo HTML（可翻页 s=0,30,60...，直出真实 URL，比 Bing 干净）
- StackExchange（tagged + query 双口径，直连优先）
- Hacker News Algolia
- 从 DDG 结果里发现并直采真实房车论坛（rvforum.net / irv2 / thorforums / mygrandrv ...）
"""
import json, os, re, sys, time, gzip, urllib.request, urllib.parse, argparse
from datetime import datetime, timezone
from patchright.sync_api import sync_playwright

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36")
OUT_DIR = "/Users/maike/Desktop/iOS副业调研_2026-11-09/采集数据/forum_extra"
OUT = os.path.join(OUT_DIR, "forum_extra.jsonl")

SE_SITES = ["stackoverflow", "apple", "webapps", "travel", "outdoors", "gaming"]
SE_TAGS = ["ios", "iphone", "app-store", "itunes", "apple-pay", "icloud",
           "xcode", "swift", "macos", "ipad", "app-store-review", "apple-watch",
           "homekit", "apple-music"]
SE_QUERIES = ["app store subscription refund", "app purchase not showing",
              "app update failed install", "app crashing after update",
              "in-app purchase receipt", "app store review rejected",
              "subscription double charged", "restore purchase missing",
              "app data lost update", "refund denied subscription",
              "app store app not available", "apple id locked out"]
SE_API = "https://api.stackexchange.com/2.3/search/advanced"

# 房车类论坛真实入口（由 DDG 发现并验证）
RV_FORUMS = [
    ("rvforum.net", "https://www.rvforum.net/forums/"),
    ("irv2", "https://www.irv2.com/forums/"),
    ("thorforums", "https://www.thorforums.com/forums/"),
    ("mygrandrv", "https://www.mygrandrv.com/forums/"),
    ("rvmotorhomes", "https://www.rvmotorhomes.com/forums/"),
    ("rvtech", "https://www.rvwithtito.com/articles/category/rv-maintenance/"),
]

DDG_QUERIES = [
    "RV leveling system app cost complaint forum",
    "RV navigation app offline problem forum",
    "RV propane tank monitor app forum",
    "RV campground booking app problem",
    "RV maintenance app subscription complaint",
    "app store subscription refund complaint forum",
    "app store review rejected developer complaint",
    "in-app purchase not showing app forum",
    "app data lost after update forum",
    "subscription double charged forum",
    "iOS app offline map problem forum",
    "app store account problem forum",
    "RV smart leveling app forum",
    "RV WiFi booster app forum problem",
    "RV solar monitor app complaint forum",
]

ledger = []


def log(m):
    print(m, flush=True)


def rec(**kw):
    kw.setdefault("collected_at", datetime.now(timezone.utc).isoformat())
    return kw


def strip_html(s):
    s = re.sub(r"<[^>]+>", " ", s or "")
    return re.sub(r"\s+", " ", s).strip()


# ---------------- StackExchange ----------------
def collect_se(fh, delay=3.2):
    stats = {"ok": 0, "fail": 0, "rows": 0, "detail": []}
    openers = [urllib.request.build_opener(urllib.request.ProxyHandler({})),
               urllib.request.build_opener()]
    jobs = []
    for site in SE_SITES:
        for q in SE_QUERIES:
            jobs.append(("q", site, q))
        for tg in SE_TAGS:
            jobs.append(("tag", site, tg))
    for kind, site, key in jobs:
        p = {"site": site, "order": "desc", "sort": "votes", "pagesize": 50,
             "filter": "default"}
        p["q" if kind == "q" else "tagged"] = key
        url = f"{SE_API}?{urllib.parse.urlencode(p)}"
        d, err = None, None
        for op in openers:
            try:
                req = urllib.request.Request(url, headers={
                    "User-Agent": UA, "Accept-Encoding": "gzip", "Accept": "application/json"})
                with op.open(req, timeout=45) as r:
                    raw = r.read()
                    if r.headers.get("Content-Encoding") == "gzip":
                        raw = gzip.decompress(raw)
                d = json.loads(raw.decode("utf-8"))
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
            time.sleep(delay * 1.4)
            continue
        items = d.get("items", [])
        for it in items:
            fh.write(json.dumps(rec(
                source="stackexchange", site=site, query=key, query_kind=kind,
                title=it.get("title"), url=it.get("link"),
                score=it.get("score"), answers=it.get("answer_count"),
                views=it.get("view_count"), is_answered=it.get("is_answered"),
                created=it.get("creation_date"), last_activity=it.get("last_activity_date"),
                tags=it.get("tags"), body_snippet=strip_html(it.get("body"))[:600],
            ), ensure_ascii=False) + "\n")
            stats["rows"] += 1
        stats["ok"] += 1
        fh.flush()
        log(f"  SE {site:13} {kind}:{key[:26]:28} {len(items):3} 条 quota={d.get('quota_remaining')}")
        time.sleep(delay)
    return stats


# ---------------- DuckDuckGo ----------------
def collect_ddg(pg, fh, queries, pages=3):
    stats = {"ok": 0, "fail": 0, "rows": 0, "detail": []}
    for q in queries:
        got = 0
        for off in range(0, pages * 10, 10):
            try:
                pg.goto(f"https://html.duckduckgo.com/html/?q={urllib.parse.quote(q)}&s={off}",
                        wait_until="domcontentloaded", timeout=40000)
                pg.wait_for_timeout(1300)
                items = pg.evaluate("""() => Array.from(document.querySelectorAll('.result, .web-result')).map(r=>{
                    const a=r.querySelector('a.result__a'); if(!a) return null;
                    const s=r.querySelector('.result__snippet');
                    let u=a.href;
                    const m=u.match(/[?&]uddg=([^&]+)/);
                    if(m){try{u=decodeURIComponent(m[1]);}catch(e){}}
                    return {t:a.innerText.trim(), u:u, s:s?s.innerText.trim():null};
                }).filter(Boolean)""")
            except Exception as e:
                stats["fail"] += 1
                stats["detail"].append(f"ddg/{q}/s{off}: {type(e).__name__} {str(e)[:60]}")
                break
            if not items:
                break
            for it in items:
                fh.write(json.dumps(rec(source="duckduckgo", query=q, offset=off,
                                        title=it["t"], url=it["u"],
                                        snippet=(it.get("s") or "")[:400]), ensure_ascii=False) + "\n")
                got += 1
                stats["rows"] += 1
            time.sleep(1.8)
        if got:
            stats["ok"] += 1
        fh.flush()
        log(f"  ddg  {q[:46]:48} {got:3} 条")
    return stats


# ---------------- Hacker News ----------------
def collect_hn(fh, queries):
    stats = {"ok": 0, "fail": 0, "rows": 0, "detail": []}
    for q in queries:
        got = 0
        try:
            u = (f"https://hn.algolia.com/api/v1/search?query={urllib.parse.quote(q)}"
                 f"&tags=story&hitsPerPage=50")
            req = urllib.request.Request(u, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=30) as r:
                d = json.loads(r.read().decode("utf-8"))
        except Exception as e:
            stats["fail"] += 1
            stats["detail"].append(f"hn/{q}: {type(e).__name__} {str(e)[:60]}")
            continue
        for h in d.get("hits", []):
            sid = h.get("story_id") or h.get("objectID")
            fh.write(json.dumps(rec(
                source="hackernews", query=q, title=h.get("title"),
                url=h.get("url") or f"https://news.ycombinator.com/item?id={sid}",
                hn_id=sid, points=h.get("points"), num_comments=h.get("num_comments"),
                author=h.get("author"), created=h.get("created_at"),
                body_snippet=(h.get("comment_text") or "")[:400],
            ), ensure_ascii=False) + "\n")
            got += 1
            stats["rows"] += 1
        if got:
            stats["ok"] += 1
        fh.flush()
        log(f"  hn   {q[:46]:48} {got:3} 条")
        time.sleep(1.4)
    return stats


# ---------------- 房车论坛直采 ----------------
def collect_rv(pg, fh, boards):
    stats = {"ok": 0, "fail": 0, "rows": 0, "detail": []}
    for name, url in boards:
        got = 0
        try:
            r = pg.goto(url, wait_until="domcontentloaded", timeout=35000)
            code = r.status if r else -1
            pg.wait_for_timeout(2500)
            items = pg.evaluate("""() => Array.from(document.querySelectorAll('a')).map(a=>{
                const t=(a.innerText||'').trim().replace(/\\s+/g,' ');
                const h=a.getAttribute('href')||'';
                if(t.length<16 || t.length>200) return null;
                if(!/thread|topic|showthread|\\/forum\\/|\\/t\\/|\\/posts\\/|\\/discussion\\//i.test(h)) return null;
                if(a.hostname && a.hostname!==location.hostname) return null;
                return {t:t, u:new URL(h,location.href).href};
            }).filter(Boolean)""")
        except Exception as e:
            stats["fail"] += 1
            stats["detail"].append(f"{name}: {type(e).__name__} {str(e)[:70]}")
            log(f"  ! {name:16} {type(e).__name__} {str(e)[:60]}")
            continue
        seen = set()
        for it in items:
            if it["u"] in seen:
                continue
            seen.add(it["u"])
            fh.write(json.dumps(rec(source="rv_forum", forum=name, forum_url=url,
                                    title=it["t"], url=it["u"]), ensure_ascii=False) + "\n")
            got += 1
            stats["rows"] += 1
        if got:
            stats["ok"] += 1
        fh.flush()
        log(f"  rv   {name:16} HTTP={code} {got:3} 条")
        time.sleep(2.2)
    return stats


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=OUT)
    ap.add_argument("--only", default="")
    a = ap.parse_args()
    os.makedirs(OUT_DIR, exist_ok=True)
    only = set(a.only.split(",")) if a.only else None

    with open(a.out, "a", encoding="utf-8") as fh:
        if only is None or "hn" in only:
            log("### Hacker News Algolia ###")
            s = collect_hn(fh, DDG_QUERIES)
            ledger.append(dict(name="hackernews", url="https://hn.algolia.com/api/v1/search",
                               http="200", rows=s["rows"], queries=len(DDG_QUERIES),
                               fails=s["fail"], fail_examples=s["detail"][:6]))
        if only is None or "se" in only:
            log("### StackExchange ###")
            s = collect_se(fh)
            ledger.append(dict(name="stackexchange", url=SE_API, http="200",
                               rows=s["rows"], queries=len(SE_SITES) * (len(SE_TAGS) + len(SE_QUERIES)),
                               fails=s["fail"], fail_examples=s["detail"][:6]))
        if only is None or "ddg" in only or "rv" in only:
            with sync_playwright() as pw:
                b = pw.chromium.launch(channel="chrome", headless=True, args=["--no-sandbox"])
                ctx = b.new_context(user_agent=UA, locale="en-US", viewport={"width": 1440, "height": 900})
                pg = ctx.new_page()
                if only is None or "ddg" in only:
                    log("### DuckDuckGo HTML ###")
                    s = collect_ddg(pg, fh, DDG_QUERIES, pages=3)
                    ledger.append(dict(name="duckduckgo", url="https://html.duckduckgo.com/html/",
                                       http="200", rows=s["rows"], queries=len(DDG_QUERIES),
                                       fails=s["fail"], fail_examples=s["detail"][:6]))
                if only is None or "rv" in only:
                    log("### RV Forums ###")
                    s = collect_rv(pg, fh, RV_FORUMS)
                    ledger.append(dict(name="rv_forums", url="多站点", http="混合",
                                       rows=s["rows"], queries=len(RV_FORUMS),
                                       fails=s["fail"], fail_examples=s["detail"][:6]))
                b.close()
    log("=== DONE ===")
    for r in ledger:
        log(f"  {r['name']:16} HTTP={r['http']:5} {r['rows']} 条  失败 {r['fails']}")
    json.dump(ledger, open(os.path.join(OUT_DIR, "_ledger.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
