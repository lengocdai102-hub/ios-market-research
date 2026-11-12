"""确定 SE 有效站点 + Google/Bing News RSS 字段结构"""
import urllib.request, json, re, time
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")
def get(u):
    return urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent": UA}), timeout=30).read().decode("utf-8","ignore")

print("A. SE 站点列表")
try:
    j = json.loads(get("https://api.stackexchange.com/2.3/sites?pagesize=100&filter=!NUXS4(QW2H(2v4)"))
    for s in j.get("items", []):
        print(f"   {s.get('site_id'):>4} {s.get('site_name',''):22} {s.get('api_site_parameter')}")
except Exception as e:
    print("  ERR", str(e)[:100])

print()
print("B. SE outdoor 站点验证")
for site in ["outdoor", "travel", "motorvehicles", "gaming", "webapps"]:
    try:
        j = json.loads(get(f"https://api.stackexchange.com/2.3/questions?site={site}&pagesize=3&order=desc&sort=votes"))
        print(f"  {site:16} -> {len(j.get('items',[]))} 条  quota={j.get('quota_remaining')}")
        for it in j.get("items", [])[:2]:
            print(f"       [{it.get('score')}] {it.get('title','')[:66]}")
    except Exception as e:
        print(f"  {site:16} ERR {str(e)[:60]}")
    time.sleep(0.4)

print()
print("C. Google News RSS 字段")
h = get("https://news.google.com/rss/search?q=%22app+store%22+subscription+complaint&hl=en-US&gl=US&ceid=US:en")
items = re.findall(r"<item>(.*?)</item>", h, re.S)
print(f"  条目数: {len(items)}")
if items:
    t = items[0]
    for f in ["title", "link", "pubDate", "source", "description"]:
        mm = re.search(rf"<{f}[^>]*>(.*?)</{f}>", t, re.S)
        print(f"    {f}: {(mm.group(1)[:90] if mm else '-')}")

print()
print("D. Bing News RSS 字段")
h2 = get("https://www.bing.com/news/search?q=rv+app+review&format=RSS")
it2 = re.findall(r"<item>(.*?)</item>", h2, re.S)
print(f"  条目数: {len(it2)}")
if it2:
    for f in ["title", "link", "pubDate", "description"]:
        mm = re.search(rf"<{f}[^>]*>(.*?)</{f}>", it2[0], re.S)
        print(f"    {f}: {(mm.group(1)[:90] if mm else '-')}")

print()
print("E. GitHub issues 字段")
j = json.loads(get("https://api.github.com/search/issues?q=app+store+subscription+in:title&sort=created&per_page=3"))
print(f"  total={j.get('total_count')}")
for it in j.get("items", [])[:3]:
    print(f"    [{it.get('state')}] {it.get('comments')}评论 {str(it.get('title'))[:60]}")
    print(f"      {it.get('html_url')}")
