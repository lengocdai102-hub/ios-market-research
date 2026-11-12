#!/usr/bin/env python3
"""任务B: 对指定 app 逐个实测内购(IAP)价格档位
方法: Apple 商品页内嵌 JSON -> Annotation{"title":"In-App Purchases","items":[{textPair leadingText/trailingText}]}
实测校验: 页面 text-pair 总数 == 解析数
"""
import json, re, sys, gzip, urllib.request, urllib.parse, os, time, hashlib

BASE = "/Users/maike/Desktop/iOS副业调研_2026-11-09"
D = f"{BASE}/采集数据"
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")

def fetch(url, timeout=45):
    h = {"User-Agent": UA, "Accept": "text/html,application/xhtml+xml,*/*;q=0.8",
         "Accept-Language": "en-US,en;q=0.9", "Accept-Encoding": "gzip, deflate"}
    req = urllib.request.Request(url, headers=h)
    r = urllib.request.urlopen(req, timeout=timeout)
    raw = r.read()
    if r.headers.get("Content-Encoding") == "gzip":
        raw = gzip.decompress(raw)
    return r.getcode(), raw.decode("utf-8", "replace")

TP_RE = re.compile(r'"leadingText"\s*:\s*"([^"]{1,120})"\s*,\s*"trailingText"\s*:\s*"\$([0-9]+(?:\.[0-9]{1,2})?)"')
ANN_RE = re.compile(r'"title"\s*:\s*"In-App Purchases"', re.I)
PRICE_RE = re.compile(r"\$([0-9]+(?:\.[0-9]{1,2})?)")

def parse_iap(body):
    """解析 Annotation In-App Purchases 块内的 textPair"""
    # 定位 In-App Purchases annotation 起点, 取其后一段 JSON 块
    results = []
    # 策略: 全文匹配所有 leadingText/trailingText 对, 但只取 In-App Purchases 之后、下一处 "title": 之前
    marks = [m.start() for m in ANN_RE.finditer(body)]
    if not marks:
        return results, 0, "no-inAppPurchases-annotation"
    total_pairs = len(TP_RE.findall(body))
    seg_start = marks[0]
    # 到下一个 annotation title 为止
    nxt = body.find('"title":', seg_start + 30)
    seg = body[seg_start: nxt if nxt > 0 else len(body)]
    for name, price in TP_RE.findall(seg):
        results.append({"name": name, "price": price, "price_num": float(price)})
    return results, total_pairs, "ok"

def probe(app_id, name, tag):
    url = f"https://apps.apple.com/us/app/id{app_id}"
    cache = f"{D}/_iap_html/{app_id}.html"
    status = "live"
    if os.path.exists(cache):
        body = open(cache, encoding="utf-8", errors="replace").read()
        status = "cached"
    else:
        try:
            code, body = fetch(url)
            os.makedirs(f"{D}/_iap_html", exist_ok=True)
            open(cache, "w", encoding="utf-8").write(body)
        except Exception as e:
            return {"app_id": app_id, "app_name": name, "error": str(e)[:120]}
    items, total_pairs, note = parse_iap(body)
    # 页面正文里出现的 $ 金额(非 IAP 块)——备用线索
    body_dollars = sorted(set(float(x) for x in PRICE_RE.findall(body)))
    uniq = {}
    for it in items:
        uniq[(it["name"], it["price"])] = it
    prices = sorted(uniq[k]["price_num"] for k in uniq)
    return {
        "app_id": app_id, "app_name": name, "tag": tag, "fetch_status": status,
        "http_page_len": len(body), "has_iap_annotation": note == "ok",
        "iap_items_raw": len(items), "text_pair_total_in_page": total_pairs,
        "iap_count": len(uniq),
        "iap_items": list(uniq.values()),
        "iap_prices": prices,
        "iap_min": prices[0] if prices else None,
        "iap_max": prices[-1] if prices else None,
        "iap_median": (prices[len(prices)//2] if len(prices) % 2 else
                       (prices[len(prices)//2 - 1] + prices[len(prices)//2]) / 2) if prices else None,
        "body_dollar_amounts_all": body_dollars[:40],
        "note": note,
    }

if __name__ == "__main__":
    targets = json.load(open(sys.argv[1]))
    out = {}
    for t in targets:
        r = probe(t["app_id"], t["app_name"], t.get("tag", ""))
        out[t["app_id"]] = r
        print(f"=== {r.get('app_name')} (id {r['app_id']}) [{r.get('fetch_status')}] ===")
        if r.get("error"):
            print("   ERR", r["error"]); continue
        print(f"   IAP块: {r['has_iap_annotation']}  原始条目 {r['iap_items_raw']}  去重 {r['iap_count']}"
              f"  页面textPair总数 {r['text_pair_total_in_page']}  校验{'通过' if r['iap_items_raw']==r['text_pair_total_in_page'] else '不匹配'}")
        for it in r["iap_items"]:
            print(f"      {it['name'][:52]:<54} ${it['price']}")
        if r["iap_prices"]:
            print(f"   价格档位: {r['iap_prices']}")
            print(f"   min ${r['iap_min']}  median ${r['iap_median']}  max ${r['iap_max']}")
        else:
            print(f"   无 IAP 价; 页面全部$金额: {r['body_dollar_amounts_all']}")
        print()
        time.sleep(1.0)
    json.dump({"_fetched_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
               "_method": "Apple 商品页 apps.apple.com/us/app/id{appId} 内嵌 JSON "
                          "Annotation{title:'In-App Purchases'} 内 textPair(leadingText,trailingText)",
               "_apps": out}, open(sys.argv[2], "w"), ensure_ascii=False, indent=1)
    print("写出", sys.argv[2])
