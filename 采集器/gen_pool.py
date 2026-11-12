"""
大规模扩充竞品池: iTunes Search API
- 关键词搜索 (房车/户外/维护/导航/露营 等)
- 分类遍历 (Travel/Utilities/Productivity/Navigation/Health 等)
- 去重, 与已有 113 个竞品合并
输出: inputs/competitor_pool.json
"""
import json, os, re, time, urllib.request, urllib.parse
from collections import defaultdict

BASE = "/Users/maike/Desktop/iOS副业调研_2026-11-09"
D = f"{BASE}/采集数据"
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")

def search(term, limit=200, country="us"):
    u = (f"https://itunes.apple.com/search?term={urllib.parse.quote(term)}"
         f"&country={country}&entity=software&limit={limit}")
    try:
        h = urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent": UA}), timeout=40).read().decode()
        return json.loads(h).get("results", [])
    except Exception as e:
        print(f"  ERR {term}: {str(e)[:50]}")
        return []

def lookup(ids, country="us", chunk=100):
    out = []
    for i in range(0, len(ids), chunk):
        part = ",".join(ids[i:i+chunk])
        u = f"https://itunes.apple.com/lookup?id={part}&country={country}&entity=software"
        try:
            h = urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent": UA}), timeout=45).read().decode()
            out.extend(json.loads(h).get("results", []))
        except Exception as e:
            print(f"  lookup ERR {str(e)[:50]}")
        time.sleep(0.35)
    return out

TERMS = [
    # 房车核心
    "rv", "rv owner", "rv maintenance", "rv leveling", "rv trip planner", "camper",
    "motorhome", "caravan", "rv gps", "rv parks", "campground", "campground map",
    "rv storage", "rv insurance", "rv maintenance checklist", "rv leveling blocks",
    "rv propane", "rv generator", "rv slide out", "rv furnace", "rv water system",
    "rv tire", "rv bearing", "rv seal", "rv roof", "rv awning", "rv steps",
    "rv towing", "rv towing checklist", "rv safety", "rv breakdown",
    # 房车相邻
    "boat maintenance", "yacht maintenance", "boat log", "marine maintenance",
    "boat checklist", "vessel maintenance", "sailing log", "fishing log",
    "hiking tracker", "camping gear checklist", "campfire cooking",
    "trailer hitch", "towing weight", "payload calculator",
    # 户外/旅行通用
    "national park", "national parks", "campground booking", "campsite reservation",
    "offline map", "gps navigation", "topo map", "hiking map",
    "weather marine", "tides", "fishing forecast", "hunting map", "public land",
    "offline maps", "topographic",
    # 维护/工具通用
    "maintenance log", "asset tracker", "equipment log", "home maintenance",
    "vehicle maintenance", "car maintenance tracker", "inspection checklist",
    "tool checklist", "inventory tracker", "warranty tracker", "service history",
    "logbook", "mileage log", "trip log", "expense log",
    # 变现/订阅
    "offline pdf", "notion offline", "budget tracker", "subscription tracker",
    "invoice generator", "receipt scanner", "tax tracker", "expense manager",
    # 细分痛点
    "warranty", "repair manual", "parts catalog", "diagram manual",
    "user manual", "offline documentation", "reference manual",
    "calibration", "torque wrench", "level tool", "spirit level",
    "measure", "unit converter", "weather station", "thermometer log",
]


# --- 第二轮扩充: 用户指定的细分领域 ---
EXTRA_TERMS = [
    "rv bearing", "rv seal", "rv propane tank", "rv leveling block", "rv leveling blocks",
    "rv wheel bearing", "rv slide seal", "rv awning motor", "rv furnace service",
    "boat motor maintenance", "marine engine log", "boat winterization", "boat checklist",
    "yacht logbook", "vessel log", "tractor service record", "trailer wheel bearing",
    "tool inventory app", "tool checklist app", "offline manual app", "offline user manual",
    "inspection checklist app", "logbook app", "warranty tracker app", "service record app",
    "maintenance scheduler app", "equipment inspection", "safety inspection checklist",
    "gps offline rv", "rv dump station", "rv propane level", "jack leveler",
]
TERMS = TERMS + EXTRA_TERMS

print(f"关键词数: {len(TERMS)}")
found = {}
for i, t in enumerate(TERMS, 1):
    rs = search(t)
    n = 0
    for r in rs:
        aid = str(r.get("trackId") or "")
        if not aid or aid in found: continue
        found[aid] = {
            "app_id": aid,
            "app_name": r.get("trackName"),
            "seller": r.get("sellerName"),
            "genre": r.get("primaryGenreName"),
            "price": r.get("price"),
            "rating_count": r.get("userRatingCount"),
            "rating": r.get("averageUserRating"),
            "genre_ids": r.get("genreIds"),
            "desc": (r.get("description") or "")[:600],
            "query_hit": t,
        }
        n += 1
    print(f"  [{i}/{len(TERMS)}] {t:32} 新增 {n:>3}  累计 {len(found)}", flush=True)
    time.sleep(0.25)

# 合并已有 113 竞品
existing = {str(c["trackId"]): c for c in json.load(open(f"{D}/dataset_competitors.json"))}
for aid, c in existing.items():
    if aid not in found:
        found[aid] = {
            "app_id": aid, "app_name": c.get("trackName"), "seller": c.get("sellerName"),
            "genre": c.get("primaryGenreName"), "price": c.get("price"),
            "rating_count": c.get("userRatingCount"), "rating": c.get("averageUserRating"),
            "genre_ids": c.get("genres"), "desc": (c.get("description") or "")[:600],
            "query_hit": "__existing__",
        }

print(f"\n合计候选池: {len(found)} 个 app")

# 用 lookup API 补全权威元数据 (只查新的)
newids = [a for a in found if a not in existing]
print(f"待 lookup 补全: {len(newids)}")
meta = {}
for i in range(0, len(newids), 100):
    part = newids[i:i+100]
    rs = lookup(part)
    for r in rs:
        aid = str(r.get("trackId") or "")
        if aid in found:
            found[aid].update({
                "rating_count": r.get("userRatingCount"),
                "rating": r.get("averageUserRating"),
                "price": r.get("price"),
                "formatted_price": r.get("formattedPrice"),
                "version": r.get("version"),
                "release_date": (r.get("releaseDate") or "")[:10],
                "current_release": (r.get("currentVersionReleaseDate") or "")[:10],
                "file_size": r.get("fileSizeBytes"),
                "min_os": r.get("minimumOsVersion"),
                "genres": r.get("genres"),
                "advisory": r.get("contentAdvisoryRating"),
                "url": r.get("trackViewUrl"),
            })
    print(f"  lookup {min(i+100,len(newids))}/{len(newids)}", flush=True)
    time.sleep(0.3)

for aid, v in found.items():
    v.setdefault("collected_at", time.strftime("%Y-%m-%d"))

os.makedirs(f"{BASE}/采集器/inputs", exist_ok=True)
json.dump(list(found.values()), open(f"{BASE}/采集器/inputs/competitor_pool.json", "w"),
          ensure_ascii=False, indent=1)

# 统计
rc = [v.get("rating_count") or 0 for v in found.values()]
print(f"\n池子统计:")
print(f"  总数 {len(found)}")
print(f"  有评分的 {sum(1 for x in rc if x>0)}")
print(f"  零评分 {sum(1 for x in rc if x==0)}")
print(f"  评分量>100 的 {sum(1 for x in rc if x>100)}")
print(f"  -> {BASE}/采集器/inputs/competitor_pool.json")
