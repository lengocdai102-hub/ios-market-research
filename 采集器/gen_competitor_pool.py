#!/usr/bin/env python3
"""建竞品大池: iTunes Search API 多关键词并发检索, 合并去重 -> competitor_pool.json"""
import json, os, threading, queue, time, urllib.request, urllib.parse

BASE = "/Users/maike/Desktop/iOS副业调研_2026-11-09"
OUT = f"{BASE}/采集器/inputs/competitor_pool.json"
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")

TERMS = [
    "RV maintenance", "RV app", "RV owner", "RV checklist", "RV trip planner",
    "RV leveling", "RV generator", "RV plumbing", "RV electrical", "RV tires",
    "RV storage", "RV campground", "RV GPS", "RV dump station", "RV service",
    "RV repair", "RV inspection", "RV insurance", "RV rental", "RV sales",
    "RV dealers", "RV parts", "RV winterizing", "RV water system", "RV sewer",
    "RV leveling blocks", "RV slide out", "RV awning", "RV fridge", "RV furnace",
    "RV inverter", "RV solar", "RV propane", "RV towing", "RV pre trip",
    "RV maintenance log", "RV maintenance tracker", "RV owner manual",
    "RV family", "RV lifestyle", "RV community", "RV route planner",
    "RV parks", "RV resorts", "RV campground reservation", "RV hookups",
    "RV maintenance checklist", "RV troubleshooting", "RV payload",
    "RV wheelbase", "RV length height", "RV towing capacity", "RV engine",
    "RV oil change", "RV filters", "RV winterization", "RV leveling guide",
    "RV hookup guide", "RV preflight", "RV height clearance", "RV route",
    "RV navigation", "RV campground finder", "RV parks campground",
    "boat maintenance", "boat maintenance log", "boat checklist", "boat tracker",
    "motorhome", "motorhome maintenance", "camper van", "camper van tracker",
    "caravan maintenance", "trailer maintenance", "motorcycle maintenance",
    "tractor maintenance log", "truck maintenance log", "vehicle maintenance log",
    "equipment maintenance log", "fleet maintenance", "home maintenance",
    "home inventory", "warranty tracker", "maintenance schedule",
    "appliance maintenance", "HVAC maintenance", "boat engine",
    "marine maintenance", "sailing log", "fishing log", "boat docking",
    "maintenance tracker", "maintenance log", "vehicle maintenance",
    "car maintenance", "car maintenance tracker", "garage log",
    "service log", "repair log", "inspection log", "checklist",
    "logbook", "garage management", "inventory", "asset tracker",
    "oil change tracker", "mileage tracker", "expense tracker car",
    "tool inventory", "parts inventory", "shop management",
    "Forest River", "Coachmen RV", "Tiffin", "Airstream", "Winnebago",
    "Jayco", "Holiday Rambler", "Newmar", "Keystone RV", "Grand Design",
    "Palomino", "Thor Motor Coach", "Cruise America", "Outdoorsy", "RVshare",
    "Recreational vehicle", "camper rental", "RV travel",
    "campground reservation", "national park campground", "campground finder",
    "camping gear checklist", "hiking gear checklist", "travel checklist",
    "pet travel", "winter checklist", "lawn mower", "pool maintenance",
    "garage door", "boat dock", "fishing tracker", "hunting log",
    "cruising", "sailing", "yacht", "jetski", "motorhome rental",
    "camper trailer", "travel trailer", "fifth wheel", "pickup camper",
    "overlanding", "van life", "van conversion", "bus conversion",
    "house on wheels", "tiny house", "homestead", "off grid",
    "solar generator", "portable power station", "generator",
]

pool = {}
lock = threading.Lock()
errs = []
q = queue.Queue()
for t in TERMS:
    q.put(t)


def worker():
    while True:
        try:
            t = q.get_nowait()
        except queue.Empty:
            return
        u = ("https://itunes.apple.com/search?term=" + urllib.parse.quote(t) +
             "&country=us&entity=software&limit=200")
        got = 0
        try:
            h = urllib.request.urlopen(
                urllib.request.Request(u, headers={"User-Agent": UA}), timeout=40
            ).read().decode("utf-8", "ignore")
            for r in json.loads(h).get("results", []):
                tid = str(r.get("trackId") or "")
                if not tid or tid == "0":
                    continue
                with lock:
                    if tid not in pool:
                        pool[tid] = {
                            "trackId": r.get("trackId"),
                            "app_id": tid,
                            "app_name": r.get("trackName"),
                            "primaryGenreName": r.get("primaryGenreName"),
                            "userRatingCount": r.get("userRatingCount"),
                            "averageUserRating": r.get("averageUserRating"),
                            "formattedPrice": r.get("formattedPrice"),
                            "sellerName": r.get("sellerName"),
                            "releaseDate": (r.get("releaseDate") or "")[:10],
                            "foundBy": [],
                        }
                    if t not in pool[tid]["foundBy"]:
                        pool[tid]["foundBy"].append(t)
                got += 1
        except Exception as e:
            with lock:
                errs.append((t, str(e)[:60]))
        print(f"  {t}: {got}", flush=True)
        q.task_done()


ts = [threading.Thread(target=worker, daemon=True) for _ in range(8)]
t0 = time.time()
for t in ts:
    t.start()
for t in ts:
    t.join()

items = sorted(pool.values(), key=lambda x: -(x.get("userRatingCount") or 0))
json.dump(items, open(OUT, "w"), ensure_ascii=False, indent=1)
print()
print(f"用时 {time.time()-t0:.0f}s")
print(f"总去重 app: {len(items)}")
for th in (50, 200, 1000, 5000):
    print(f"  评分量>={th}: {sum(1 for x in items if (x.get('userRatingCount') or 0)>=th)}")
print(f"错误项: {len(errs)} -> {errs[:5]}")
print(f"-> {OUT}")
