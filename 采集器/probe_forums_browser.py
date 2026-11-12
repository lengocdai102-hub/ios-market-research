"""用真实 Chrome (patchright) 探测被 403 的论坛源能否通过"""
import time, json
from patchright.sync_api import sync_playwright

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")

TARGETS = [
    ("Reddit r/RV",        "https://www.reddit.com/r/RV/"),
    ("Reddit r/RVs",       "https://www.reddit.com/r/RVs/"),
    ("Reddit r/camping",   "https://www.reddit.com/r/camping/"),
    ("RVforum",            "https://www.rvforum.net/"),
    ("RV Talk",            "https://www.rvtalk.com/"),
    ("Motorhome Forum",    "https://www.motorhomeforum.com/"),
    ("TravelTrailsRV",     "https://www.traveltrailsrv.com/"),
    ("iRV2",               "https://www.irv2.com/"),
    ("The Motorhome Man",  "https://www.themotorhomeman.com/"),
    ("Quora",              "https://www.quora.com/"),
]

print("=" * 76)
print("真实 Chrome 模式探测")
print("=" * 76)
res = []
with sync_playwright() as p:
    br = p.chromium.launch(channel="chrome", headless=True)
    ctx = br.new_context(user_agent=UA, locale="en-US")
    pg = ctx.new_page()
    for name, url in TARGETS:
        r = {"name": name, "url": url}
        try:
            resp = pg.goto(url, wait_until="domcontentloaded", timeout=45000)
            pg.wait_for_timeout(2500)
            r["status"] = resp.status if resp else None
            txt = pg.content().lower()
            r["cf"] = "just a moment" in txt or "checking your browser" in txt
            r["login"] = bool(pg.query_selector("input[name='password']")) and "reddit" in url
            body = pg.inner_text("body")[:4000]
            r["chars"] = len(body)
            r["title"] = pg.title()[:60]
            # 结构化内容探针
            r["n_article"] = len(pg.query_selector_all("article, .post, .thread, shreddit-post, [data-testid='post-container']"))
            r["n_link"] = len(pg.query_selector_all("a"))
            r["verdict"] = "OK" if r["status"] == 200 and not r["cf"] and r["chars"] > 500 else "FAIL"
        except Exception as e:
            r["verdict"] = "ERR"
            r["err"] = str(e)[:70]
        res.append(r)
        print(f"  {r['verdict']:5} {name:22} status={r.get('status')} 字符数={r.get('chars',0):>6} "
              f"结构条目={r.get('n_article',0):>3} 链接={r.get('n_link',0):>4}  {r.get('title','')[:34]}")
        time.sleep(1.2)
    br.close()

print()
ok = [r["name"] for r in res if r.get("verdict") == "OK"]
print(f"浏览器模式可用: {len(ok)}/{len(res)} -> {ok}")
json.dump(res, open("/tmp/forum_probe_browser.json", "w"), ensure_ascii=False, indent=2)
