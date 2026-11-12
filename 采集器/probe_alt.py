"""探测第三方案: 归档API / 新闻RSS / 通用搜索引擎RSS"""
import urllib.request, urllib.error, json, re, time
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")

def probe(name, url):
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "en-US,en;q=0.9"})
        with urllib.request.urlopen(req, timeout=30) as r:
            b = r.read()
            return r.getcode(), len(b), b.decode("utf-8", "ignore")
    except urllib.error.HTTPError as e:
        return e.code, 0, ""
    except Exception as e:
        return None, 0, str(e)[:60]

CANDS = [
    ("PullPush 帖子",   "https://api.pullpush.io/reddit/search/submission/?q=rv+app&size=10"),
    ("PullPush 评论",   "https://api.pullpush.io/reddit/search/comment/?q=app+subscription&size=10"),
    ("PullPush subreddit","https://api.pullpush.io/reddit/search/submission/?subreddit=RV&size=10"),
    ("Google News RSS","https://news.google.com/rss/search?q=rv+app+iphone&hl=en-US&gl=US&ceid=US:en"),
    ("Bing News RSS",  "https://www.bing.com/news/search?q=rv+app&format=RSS"),
    ("Google 博客搜索", "https://news.google.com/rss/search?q=%22App+Store%22+rejected+app&hl=en-US&gl=US&ceid=US:en"),
    ("Reddit via RSS proxy", "https://www.reddit.com/r/RV/top.rss"),
    ("Reddit JSON w/ UA", "https://www.reddit.com/r/RV/top.json"),
    ("Reddit via teddit", "https://teddit.net/r/RV/"),
    ("Reddit via libreddit","https://lr.artemislena.eu/r/RV/"),
    ("Reddit via redlib", "https://redlib.catsarch.com/r/RV/"),
    ("SE 房车站点",      "https://api.stackexchange.com/2.3/questions?site=outdoor&pagesize=20&order=desc&sort=votes"),
    ("SE all sites RV",  "https://api.stackexchange.com/2.3/search/advanced?order=desc&sort=votes&q=RV&site=stackexchange&pagesize=20"),
    ("GitHub 讨论搜索",  "https://api.github.com/search/issues?q=app+store+subscription+in:title&sort=created&per_page=10"),
    ("GitHub 代码搜索",  "https://api.github.com/search/repositories?q=ios+rv+app&sort=stars&per_page=10"),
    ("App Store 评论 RSS(旧)", "https://itunes.apple.com/us/rss/customerreviews/id=1443835927/sortBy=mostRecent/json"),
    ("Arxiv",            "http://export.arxiv.org/api/query?search_query=all:iOS+app&max_results=5"),
]

print("=" * 82)
print("第三方案探测: 归档API / 新闻RSS / 搜索引擎")
print("=" * 82)
for name, url in CANDS:
    code, n, txt = probe(name, url)
    if code == 200:
        ni = len(re.findall(r"<item[ >]", txt)) + len(re.findall(r'"title":', txt)) + len(re.findall(r'"data":\s*\[', txt))
        print(f"  ✔ {name:24} 200 {n//1024:>5}KB 条目≈{ni:<4} {txt[:52].strip()[:48]!r}")
    else:
        print(f"  ✘ {name:24} {code} {txt[:44]}")
    time.sleep(0.5)
