#!/usr/bin/env python3
"""对指定 app 列表批量采集 IAP 价格 (直连 apps.apple.com)
复用 probe_iap_prices.py 的解析逻辑
"""
import json, os, sys, time, gzip, urllib.request, re, concurrent.futures

BASE = "/Users/maike/Desktop/iOS副业调研_2026-11-09"
D = f"{BASE}/采集数据"
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")
ANN_RE = re.compile(r'"title"\s*:\s*"In-App Purchases"', re.I)
TP_RE = re.compile(r'"leadingText"\s*:\s*"([^"]{1,140})"\s*,\s*"trailingText"\s*:\s*"\$([0-9]+(?:\.[0-9]{1,2})?)"')

def fetch(url, timeout=45):
    h = {"User-Agent": UA, "Accept": "text/html,application/xhtml+xml,*/*;q=0.8",
         "Accept-Language": "en-US,en;q=0.9", "Accept-Encoding": "gzip, deflate"}
    r = urllib.request.urlopen(urllib.request.Request(url, headers=h), timeout=timeout)
    raw = r.read()
    if r.headers.get("Content-Encoding") == "gzip":
        raw = gzip.decompress(raw)
    return raw.decode("utf-8", "replace")

def parse(body):
    marks = [m.start() for m in ANN_RE.finditer(body)]
    if not marks: return [], 0
    total = len(TP_RE.findall(body))
    s = marks[0]
    nxt = body.find('"title":', s + 30)
    seg = body[s: nxt if nxt > 0 else len(body)]
    return TP_RE.findall(seg), total

def one(app):
    aid = app["app_id"]
    cache = f"{D}/_iap_html/{aid}.html"
    status = "live"
    if os.path.exists(cache):
        body = open(cache, encoding="utf-8", errors="replace").read(); status = "cached"
    else:
        try:
            body = fetch(f"https://apps.apple.com/us/app/id{aid}")
            os.makedirs(f"{D}/_iap_html", exist_ok=True)
            open(cache, "w", encoding="utf-8").write(body)
        except Exception as e:
            return {"app_id": aid, "app_name": app.get("app_name"), "error": str(e)[:100]}
    pairs, total = parse(body)
    uniq = {}
    for name, price in pairs:
        uniq[(name, price)] = {"name": name, "price": price, "price_num": float(price)}
    prices = sorted(v["price_num"] for v in uniq.values())
    return {"app_id": aid, "app_name": app.get("app_name"), "seller": app.get("seller"),
            "genre": app.get("genre"), "urc": app.get("urc"), "fetch_status": status,
            "has_iap_block": bool(pairs), "iap_items_raw": len(pairs),
            "text_pair_total_in_page": total, "iap_count": len(uniq),
            "iap_items": list(uniq.values()), "iap_prices": prices,
            "iap_min": prices[0] if prices else None, "iap_max": prices[-1] if prices else None,
            "iap_median": (prices[len(prices)//2] if len(prices) % 2 else
                           (prices[len(prices)//2-1]+prices[len(prices)//2])/2) if prices else None}

if __name__ == "__main__":
    apps = json.load(open(sys.argv[1]))
    out_path = sys.argv[2]
    res = {}
    done = 0
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as ex:
        futs = {ex.submit(one, a): a for a in apps}
        for f in concurrent.futures.as_completed(futs):
            r = f.result(); res[r["app_id"]] = r; done += 1
            if done % 25 == 0: print(f"  {done}/{len(apps)}", flush=True)
    json.dump({"_fetched_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
               "_method": "apps.apple.com/us/app/id{appId} 内嵌 JSON Annotation In-App Purchases -> textPair",
               "_apps": res}, open(out_path, "w"), ensure_ascii=False, indent=1)
    ok = sum(1 for v in res.values() if v.get("has_iap_block"))
    err = sum(1 for v in res.values() if v.get("error"))
    print(f"完成 {len(res)} | 有IAP {ok} | 无IAP {len(res)-ok-err} | 错误 {err} -> {out_path}")
