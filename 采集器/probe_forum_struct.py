"""验证 old.reddit 提取结构化帖子 + SE API + HN Algolia 的字段结构"""
import urllib.request, json, re, time
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")

def get(u):
    return urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent": UA}), timeout=35).read().decode("utf-8","ignore")

print("A. old.reddit r/RV 帖子提取")
try:
    h = get("https://old.reddit.com/r/RV/top/?sort=top&t=year")
    from scrapling.parser import Selector
    s = Selector(h)
    things = s.css("div.thing[data-fullname]")
    print(f"  div.thing 数: {len(things)}")
    for t in things[:4]:
        a = t.css("a.title")
        print(f"    [{t.attrib.get('data-score')}] {a[0].text[:66] if a else '?'}")
        print(f"        评论数={t.attrib.get('data-comments-count')} 作者={t.attrib.get('data-author')}")
        c = t.css("p.comment-body")
        if c: print(f"        正文: {c[0].text[:100].strip()}")
except Exception as e:
    print("  ERR", str(e)[:120])

print()
print("B. old.reddit 搜索能力 (关键词定向)")
try:
    h = get("https://old.reddit.com/r/RV/search/?q=app&restrict_sr=on&sort=relevance&t=all")
    s = Selector(h)
    th = s.css("div.thing[data-fullname]")
    print(f"  搜索 'app' -> {len(th)} 个结果")
    for t in th[:4]:
        a = t.css("a.title")
        print(f"    [{t.attrib.get('data-score')}] {a[0].text[:64] if a else '?'}")
except Exception as e:
    print("  ERR", str(e)[:120])

print()
print("C. StackExchange API 字段")
try:
    j = json.loads(get("https://api.stackexchange.com/2.3/search/advanced?order=desc&sort=votes&q=app+store+subscription&site=stackoverflow&pagesize=3&filter=withbody"))
    for it in j.get("items", [])[:3]:
        print(f"  score={it.get('score')} answers={it.get('answer_count')} views={it.get('view_count')} tags={it.get('tags')}")
        print(f"    title: {it.get('title','')[:70]}")
        body = re.sub(r"<[^>]+>", " ", it.get("body",""))[:110]
        print(f"    body: {body.strip()}")
    print("  quota:", j.get("quota_remaining"))
except Exception as e:
    print("  ERR", str(e)[:120])

print()
print("D. HN Algolia 字段")
try:
    j = json.loads(get("https://hn.algolia.com/api/v1/search?query=app+store+subscription&tags=story&hitsPerPage=3"))
    for h in j.get("hits", [])[:3]:
        print(f"  points={h.get('points')} comments={h.get('num_comments')} {h.get('created_at','')[:10]}")
        print(f"    title: {h.get('title','')[:70]}")
except Exception as e:
    print("  ERR", str(e)[:120])
