"""查证: 评论重复记录(带正文 + 全None 成对) 的真实结构, 以及评分分布是否抓对对象"""
import re, json, urllib.request
from scrapling.parser import Selector

UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
AID = "1443835927"   # Outdoorsy

def get(u):
    return urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent": UA}), timeout=40).read().decode("utf-8", "ignore")

html = get(f"https://apps.apple.com/us/app/id{AID}?see-all=reviews")
s = Selector(html)

print("=" * 72)
print("A. 评分分布 star-row 结构")
els = s.css("[data-testid^='star-row']")
print(f"  找到 {len(els)} 个 star-row")
for el in els[:6]:
    print("  testid:", el.attrib.get("data-testid"), "| text:", repr((el.text or "")[:50]))
    for inner in el.css("[style*='width']"):
        print("     inner:", inner.attrib.get("style"), "|", repr((inner.text or "")[:20]))

print()
print("B. star-row 容器上下文 (找总评分数来源)")
m = re.search(r"star-row-5", html)
if m:
    seg = html[max(0, m.start()-2000):m.start()+300]
    for pat in [r'(\d[\d,]*)\s*Ratings', r'"ratingValue"\s*:\s*([\d.]+)', r'"ratingCount"\s*:\s*(\d+)', r'"totalNumberOfRatings"']:
        f = re.findall(pat, seg) or re.findall(pat, html)
        if f: print(f"  {pat} -> {f[:6]}")

print()
print("C. 评论条目容器结构")
for sel in ["[data-testid*='review']", "li[class*='review']", "div[class*='review']", "section[class*='review']"]:
    els2 = s.css(sel)
    if els2:
        print(f"  {sel} -> {len(els2)} 个")
        for e in els2[:3]:
            cls = e.attrib.get("class") or ""
            print("    class:", cls[:100])
            print("    text:", repr((e.text or "")[:100]))
        break

print()
print("D. 'N Stars' 出现次数与上下文")
hits = [mm.start() for mm in re.finditer(r"[1-5] Stars", html)]
print(f"  出现 {len(hits)} 次")
if hits:
    i = hits[0]
    print("\n  --- 第一处上下文 ---")
    print(html[max(0, i-1100):i+200].replace("\n", " ")[:1300])
