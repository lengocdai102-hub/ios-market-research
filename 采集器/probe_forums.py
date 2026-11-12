"""
探测论坛/UGC 数据源可达性
维度: HTTP状态 / Cloudflare拦截 / 是否需登录 / 有无结构化数据 / RSS可用性
"""
import urllib.request, urllib.error, json, re, time

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")

CANDIDATES = [
    # (名称, 类型, URL)
    ("Reddit r/RV",              "reddit",  "https://www.reddit.com/r/RV/top.json?t=month&limit=25"),
    ("Reddit r/RVs",             "reddit",  "https://www.reddit.com/r/RVs/top.json?t=month&limit=25"),
    ("Reddit r/camping",         "reddit",  "https://www.reddit.com/r/camping/top.json?t=month&limit=25"),
    ("Reddit r/mobileappdev",    "reddit",  "https://www.reddit.com/r/mobileappdev/top.json?t=month&limit=25"),
    ("Reddit r/AppStore",        "reddit",  "https://www.reddit.com/r/AppStore/top.json?t=month&limit=25"),
    ("RVforum",                  "discourse","https://www.rvforum.net/"),
    ("RV Talk (Good RV)",        "forum",   "https://www.rvtalk.com/"),
    ("RVWithTito",               "forum",   "https://www.rvwithtito.com/"),
    ("Motorhome Forum",          "forum",   "https://www.motorhomeforum.com/"),
    ("The Motorhome Man",        "forum",   "https://www.themotorhomeman.com/"),
    ("TravelTrailsRV",           "forum",   "https://www.traveltrailsrv.com/"),
    ("iRV2",                     "forum",   "https://www.irv2.com/"),
    ("StackExchange-iOS",        "se",      "https://api.stackexchange.com/2.3/questions?site=stackoverflow&tagged=ios&pagesize=20&order=desc&sort=votes"),
    ("StackExchange-Programming", "se",     "https://api.stackexchange.com/2.3/questions?site=stackoverflow&tagged=swift&pagesize=20&order=desc&sort=votes"),
    ("Quora RV",                 "quora",   "https://www.quora.com/"),
    ("Discussions.apple.com",    "apple",   "https://discussions.apple.com/search?q=app+subscription"),
    ("Apple Support",            "apple",   "https://support.apple.com/en-us/thread/"),
    ("Google Play 评论",          "play",    "https://play.google.com/store/apps/details?id=com.google.android.apps.maps&hl=en_US&gl=US"),
]

def probe(name, kind, url):
    out = {"name": name, "kind": kind, "url": url}
    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": UA, "Accept-Language": "en-US,en;q=0.9",
            "Accept": "text/html,application/xhtml+xml,application/json;q=0.9,*/*;q=0.8",
        })
        with urllib.request.urlopen(req, timeout=30) as r:
            body = r.read()
            out["status"] = r.getcode()
            out["bytes"] = len(body)
            txt = body.decode("utf-8", "ignore")
            low = txt.lower()
            out["cloudflare"] = ("just a moment" in low or "cf-browser-verification" in low
                                 or "checking your browser" in low or "challenge-platform" in low)
            out["login_wall"] = bool(re.search(r"log in to continue|sign in to continue|please log in|create an account to", low))
            out["blocked_403"] = out["status"] == 403
            out["paywall"] = bool(re.search(r"subscribe to (read|continue)|become a member to", low))
            # 内容信号
            out["has_json_ld"] = "application/ld+json" in low
            out["has_rss"] = bool(re.search(r'<link[^>]+type=["\']application/rss', low))
            out["title"] = (re.search(r"<title[^>]*>(.*?)</title>", txt, re.S | re.I).group(1).strip()[:60]
                            if re.search(r"<title[^>]*>(.*?)</title>", txt, re.S | re.I) else "")
            if kind == "reddit" and out["status"] == 200:
                try:
                    j = json.loads(txt)
                    out["items"] = len(j.get("data", {}).get("children", []))
                    out["sample_title"] = j["data"]["children"][0]["data"].get("title", "")[:60]
                except Exception as e:
                    out["json_err"] = str(e)[:60]
            if kind == "se" and out["status"] == 200:
                try:
                    j = json.loads(txt)
                    out["items"] = len(j.get("items", []))
                except Exception:
                    pass
            out["verdict"] = "OK" if out["status"] == 200 and not out["cloudflare"] else (
                "CF" if out["cloudflare"] else f"HTTP{out['status']}")
    except urllib.error.HTTPError as e:
        out["status"] = e.code
        out["verdict"] = f"HTTP{e.code}"
    except Exception as e:
        out["verdict"] = "ERR"
        out["err"] = str(e)[:70]
    return out

print("=" * 78)
print("论坛/UGC 数据源可达性探测")
print("=" * 78)
res = []
for n, k, u in CANDIDATES:
    r = probe(n, k, u)
    res.append(r)
    flag = "✔" if r.get("verdict") == "OK" else "✘"
    extra = []
    if r.get("items"): extra.append(f"items={r['items']}")
    if r.get("cloudflare"): extra.append("CF拦截")
    if r.get("login_wall"): extra.append("需登录")
    if r.get("paywall"): extra.append("付费墙")
    if r.get("has_rss"): extra.append("有RSS")
    if r.get("bytes"): extra.append(f"{r['bytes']//1024}KB")
    print(f"  {flag} {n:26} {str(r.get('verdict')):9} {' '.join(extra)}  {r.get('title','')[:40]}")
    time.sleep(0.8)

print()
ok = [r for r in res if r.get("verdict") == "OK"]
print(f"可直接用: {len(ok)}/{len(res)}  -> {[r['name'] for r in ok]}")
json.dump(res, open("/tmp/forum_probe.json", "w"), ensure_ascii=False, indent=2)
