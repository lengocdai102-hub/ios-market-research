#!/usr/bin/env python3
"""探测 IAP 价格抓取路径: 多路径实测
"""
import json, re, urllib.request, urllib.parse, gzip, io

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")
PROXY = "http://127.0.0.1:7897"

def fetch(url, use_proxy=True, timeout=40):
    h = {"User-Agent": UA, "Accept": "text/html,application/json,*/*",
         "Accept-Language": "en-US,en;q=0.9", "Accept-Encoding": "gzip, deflate"}
    opener = urllib.request.build_opener(
        urllib.request.ProxyHandler({"http": PROXY, "https": PROXY}) if use_proxy
        else urllib.request.ProxyHandler({}))
    req = urllib.request.Request(url, headers=h)
    r = opener.open(req, timeout=timeout)
    raw = r.read()
    if r.headers.get("Content-Encoding") == "gzip":
        raw = gzip.decompress(raw)
    return r.getcode(), raw.decode("utf-8", "replace")

APPID = "1508523800"   # 占位，后面换真实付费 app

print("=" * 70)
print("路径1: apps.apple.com 商品页 HTML, 搜 IAP 字段")
for use_proxy in (True, False):
    try:
        code, body = fetch(f"https://apps.apple.com/us/app/id{APPID}", use_proxy)
        print(f"  proxy={use_proxy} HTTP {code} len={len(body)}")
        for kw in ["inAppPurchase", "inAppPurchases", "offers", "In-App Purchase",
                   "inAppPurchasePrice", "priceFormatted", "productId", "subscription"]:
            print(f"     {kw:22} 出现 {body.count(kw)} 次")
    except Exception as e:
        print(f"  proxy={use_proxy} ERR {str(e)[:90]}")

print("=" * 70)
print("路径2: AmpAPI / Apple 的 shoebox JSON")
for u in [
    f"https://apps.apple.com/us/app/id{APPID}?see-all=in-app-purchases",
    f"https://amp-api.apps.apple.com/v1/catalog/us/apps/{APPID}?platform=web&additionalPlatforms=appletv,ipad,iphone,mac",
    f"https://amp-api.apps.apple.com/v1/catalog/us/apps/{APPID}/inAppPurchases?platform=web",
]:
    try:
        code, body = fetch(u)
        print(f"  HTTP {code} len={len(body)}  {u[:80]}")
        print(f"     片段: {body[:220]}")
    except Exception as e:
        print(f"  ERR {str(e)[:80]}  {u[:70]}")

print("=" * 70)
print("路径3: rss / 其它")
for u in [
    f"https://itunes.apple.com/us/lookup?id={APPID}",
    f"https://itunes.apple.com/WebObjects/MZStore.woa/wa/viewTop?genreId=36",
]:
    try:
        code, body = fetch(u)
        print(f"  HTTP {code} len={len(body)}  {u[:70]}")
    except Exception as e:
        print(f"  ERR {str(e)[:80]}  {u[:60]}")
