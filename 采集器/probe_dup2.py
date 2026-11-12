"""查清评论解析的真实来源: 20 条从哪来的, 为何带正文/None 成对"""
import re, json, urllib.request
from scrapling.parser import Selector

UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
AID = "1443835927"

def get(u):
    return urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent": UA}), timeout=40).read().decode("utf-8", "ignore")

html = get(f"https://apps.apple.com/us/app/id{AID}?see-all=reviews")
s = Selector(html)

print("A. grid 内 li 数量")
grid = s.css("[data-test-id='grid']")
print("  grid:", len(grid))
if grid:
    lis = grid[0].css("li")
    print("  grid > li:", len(lis))
    for i, li in enumerate(lis[:3]):
        print(f"  --- li[{i}] class={li.attrib.get('class')}")
        # 找 h3 title
        h3 = li.css("h3")
        if h3: print("      h3:", repr(h3[0].text[:70]))
        ol = li.css("ol[aria-label]")
        if ol: print("      stars aria-label:", ol[0].attrib.get("aria-label"))
        print("      text[:150]:", repr((li.text or "")[:150]))

print()
print("B. 全页 review 相关 class 统计")
from collections import Counter
cls = Counter()
for e in s.css("[class*='review']"):
    c = e.attrib.get("class") or ""
    for part in c.split():
        if "review" in part: cls[part] += 1
print(" ", dict(cls))

print()
print("C. 页面内嵌 JSON 数据块")
for pat in [r'<script[^>]*id="[^"]*json[^"]*"[^>]*>(.*?)</script>', r'<script[^>]*type="application/json"[^>]*>(.*?)</script>']:
    for mm in re.finditer(pat, html, re.S):
        body = mm.group(1)
        print(f"  len={len(body)}  head={body[:150]}")

print()
print("D. 'N Stars' 全部位置 + 前后 200 字")
for mm in list(re.finditer(r"[1-5] Stars", html)):
    i = mm.start()
    ctx = html[max(0,i-260):i+40].replace("\n"," ")
    print(f"  @{i}: ...{ctx[-300:]}")
