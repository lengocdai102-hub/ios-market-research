"""生成各维度的目标清单文件"""
import json, os, urllib.request, urllib.parse, time, re

UA="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
OUT="/Users/maike/Desktop/iOS副业调研_2026-11-09/采集器/inputs"
os.makedirs(OUT, exist_ok=True)

def jget(u):
    req=urllib.request.Request(u, headers={"User-Agent":UA})
    with urllib.request.urlopen(req,timeout=45) as r:
        return json.loads(r.read().decode())

# --- 竞品池: 房车/露营/维护/户外 相关搜索词 ---
TERMS = [
 "RV maintenance","RV app","RV owner","motorhome maintenance","camper van",
 "RV leveling","RV generator","RV plumbing","RV electrical","RV tires",
 "RV checklist","RV trip planner","campground reservation","RV storage",
 "car maintenance","home maintenance checklist","HVAC maintenance","boat maintenance",
 "RVServiceVault","RV Keeper","RV Pocket","My General RV","Recreational vehicle",
]
pool = {}
for t in TERMS:
    try:
        j = jget(f"https://itunes.apple.com/search?term={urllib.parse.quote(t)}&country=us&entity=software&limit=30")
        for r in j.get("results",[]):
            tid=r.get("trackId")
            if not tid: continue
            gen=r.get("primaryGenreName","")
            nm=r.get("trackName","")
            # 只保留房车/露营/维护/户外相关
            blob=(nm+" "+gen).lower()
            if any(k in blob for k in ["rv","recreational","camper","motorhome","caravan","maintenance","marina","boat","overland","airstream","campervan","travel trailer"]):
                pool[tid]={"trackId":tid,"trackName":nm,"primaryGenreName":gen,
                           "userRatingCount":r.get("userRatingCount"),
                           "averageUserRating":r.get("averageUserRating"),
                           "formattedPrice":r.get("formattedPrice"),
                           "sellerName":r.get("sellerName"),
                           "releaseDate":r.get("releaseDate"),
                           "foundBy":t}
        time.sleep(0.4)
    except Exception as e:
        print(f"FAIL {t}: {e}")

# 补: 榜单里 Travel/Lifestyle/Utilities 类出现的房车相关 app
for gid,gn in [("6020","Travel"),("6012","Lifestyle"),("6016","Navigation"),("6024","Medical"),("6006","Utilities")]:
    try:
        j=jget(f"https://itunes.apple.com/us/rss/topfreeapplications/limit=200/genre={gid}/json")
        for e in j.get("feed",{}).get("entry",[]):
            nm=e["im:name"]["label"]
            if re.search(r"\bRV\b|camper|motorhome|caravan|overland|airstream|maintenance", nm, re.I):
                m=re.search(r"id(\d+)", e.get("id",{}).get("label",""))
                if m and int(m.group(1)) not in pool:
                    pool[int(m.group(1))]={"trackId":int(m.group(1)),"trackName":nm,
                        "primaryGenreName":gn,"foundBy":f"chart_{gn}"}
    except Exception as e:
        print(f"chart {gn} FAIL: {e}")

apps = list(pool.values())
apps.sort(key=lambda x: -(x.get("userRatingCount") or 0))
json.dump(apps, open(f"{OUT}/competitor_ids.json","w"), ensure_ascii=False, indent=2)
print(f"竞品池: {len(apps)} 个")

# --- 社区查询词 ---
QUERIES = [
 "app store subscription cancel","app store subscription refund","app store free trial",
 "subscription scam app","app store app not working","app store app crashed",
 "app store update problem","app store purchase not showing","app store billing issue",
 "app store alternative to","app store paid app worth it","app store review complaint",
 "rv maintenance","rv owner problems","motorhome repair","camper van problems",
 "app developers small business","solo developer app revenue","indie app monetization",
 "app store keyword discoverability","app store search not working","app store reviews not showing",
]
json.dump(QUERIES, open(f"{OUT}/community_queries.json","w"), ensure_ascii=False, indent=2)
print(f"社区查询词: {len(QUERIES)}")

# --- 竞品搜索词 (lookup 维度) ---
json.dump(TERMS, open(f"{OUT}/lookup_terms.json","w"), ensure_ascii=False, indent=2)
print(f"lookup 词: {len(TERMS)}")
