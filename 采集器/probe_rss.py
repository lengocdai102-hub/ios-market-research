"""绕行方案探测: RSS / JSON API / 搜索引擎缓存 / 代理"""
import urllib.request, urllib.error, json, re, time
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")

def probe(name, url, hdr=None):
    h = {"User-Agent": UA, "Accept-Language": "en-US,en;q=0.9"}
    if hdr: h.update(hdr)
    try:
        req = urllib.request.Request(url, headers=h)
        with urllib.request.urlopen(req, timeout=30) as r:
            b = r.read()
            return r.getcode(), len(b), b.decode("utf-8", "ignore")
    except urllib.error.HTTPError as e:
        return e.code, 0, ""
    except Exception as e:
        return None, 0, str(e)[:70]

CANDS = [
    # 论坛 RSS —— 通常不走 CF 挑战
    ("RVWithTito 搜索RSS", "https://www.rvwithtito.com/search.rss?query=app+OR+iphone&o=relevance"),
    ("RVWithTito 论坛RSS", "https://www.rvwithtito.com/forums/rv-app.rss"),
    ("RVforum RSS",        "https://www.rvforum.net/forums/rss/1-general-discussion/"),
    ("iRV2 RSS",           "https://www.irv2.com/forums/rss/1-general-discussion/"),
    ("RV Talk RSS",        "https://www.rvtalk.com/external.php?type=RSS2"),
    ("MotorhomeForum RSS", "https://www.motorhomeforum.com/forums/rss/1-general-discussion/"),
    ("TravelTrailsRSS",    "https://www.traveltrailsrv.com/forums/rss/1-general-discussion/"),
    # Reddit 官方/镜像
    ("Reddit .rss",        "https://www.reddit.com/r/RV/.rss?limit=25"),
    ("Reddit old.reddit",  "https://old.reddit.com/r/RV/"),
    ("Reddit rss:reddit",  "https://www.reddit.com/r/RV/top/.rss"),
    # StackExchange 全站
    ("SE RV questions",    "https://api.stackexchange.com/2.3/search/advanced?order=desc&sort=votes&q=recreational%20vehicle&site=outdoor&pagesize=20"),
    ("SE iOS App Store",   "https://api.stackexchange.com/2.3/search/advanced?order=desc&sort=votes&q=app%20store%20subscription&site=stackoverflow&pagesize=20"),
    ("SE WebApplications","https://api.stackexchange.com/2.3/questions?site=webapps&pagesize=20&order=desc&sort=votes"),
    # Hacker News (Algolia API, 无防护)
    ("HN Algolia",         "https://hn.algolia.com/api/v1/search?query=ios%20app%20subscription&tags=story&hitsPerPage=20"),
    ("HN Algolia show",    "https://hn.algolia.com/api/v1/search_by_date?query=app%20store%20rejected&tags=story&hitsPerPage=20"),
    # 其它 UGC
    ("Quora RSS",          "https://www.quora.com/feed"),
    ("Discussions Apple RSS", "https://discussions.apple.com/feed.rss"),
    ("Apple Support RSS",  "https://support.apple.com/en-us/thread/feed.rss"),
    ("Google Play 评论解析", "https://play.google.com/store/apps/details?id=com.google.android.apps.maps&hl=en_US&gl=US&showAllReviews=true"),
]

print("=" * 80)
print("绕行方案探测 (RSS / API)")
print("=" * 80)
for name, url in CANDS:
    code, n, txt = probe(name, url)
    if code == 200:
        # 判断是否有结构化条目
        n_item = len(re.findall(r"<item[ >]", txt)) + len(re.findall(r'"title":', txt))
        print(f"  ✔ {name:26} 200 {n//1024:>5}KB  条目≈{n_item:<5} {txt[:60].strip()[:52]!r}")
    else:
        print(f"  ✘ {name:26} {code} {txt[:50]}")
    time.sleep(0.5)
