"""
深挖 K 修正版: 赢家存活性复核
上一版两个错误:
  1) app_id 靠猜 -> 返回 0 条。改为从竞品池按名称反查真实 trackId
  2) 判定规则过严 -> "停更>18月"判死, 但 Errands To-Do List 2017-10 后没更新
     却在 2026-11-07 仍在收评论 => 停更 != 已死
修正判定: 以【评论到达时间】为准
  活跃   : 近 12 个月有新评论
  停滞   : 近 12-24 个月有新评论
  已死   : 近 24 个月无任何新评论
版本更新时间只作参考, 不作判据
"""
import json, os, statistics, urllib.request, time
from collections import defaultdict
from datetime import datetime, timezone

D = "/Users/maike/Desktop/iOS副业调研_2026-11-09/采集数据"
BASE = "/Users/maike/Desktop/iOS副业调研_2026-11-09"
NOW = datetime(2026, 11, 10, tzinfo=timezone.utc)
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/131.0.0.0 Safari/537.36"

pool = json.load(open(f"{D}/_expanded_competitors.json"))

# ---- 按名称索引池 ----
byname = {}
for aid, a in pool.items():
    n = (a.get("trackName") or "").strip()
    if n: byname.setdefault(n.lower(), (aid, a))

# 赢家名单(来自 deepdive_winners.py 的结论)
W = ["Lists To do","GPS Tracks","Errands To-To List","Errands To-Do List","Boondocking",
     "RV Dump Stations","USFS & BLM Campgrounds","Bubble Level 2022",
     "Speedometer 55 GPS Speed & HUD","Fishing Knots FishPlanet","Packr Travel Packing List",
     "MapChart App","Guru Maps","Vehicle Maintenance Tracker","Checklist – Simple Task Lists",
     "Checklist - Simple Task Lists","Progressive","Fishing Planet","GPS Tracking"]

def find(name):
    n = name.strip().lower()
    if n in byname: return byname[n]
    # 去掉标点再试
    k = n.replace("–","-").replace("—","-")
    for kk,(aid,a) in byname.items():
        if kk.replace("–","-").replace("—","-")==k: return (aid,a)
    # 包含匹配
    for kk,(aid,a) in byname.items():
        if n in kk or kk in n: return (aid,a)
    return None

resolved = {}
for nm in W:
    r = find(nm)
    if r:
        resolved[nm] = r[0]
        print(f"  解析 {nm[:36]:38s} -> {r[0]:>12}  ({r[1].get('trackName')})")
    else:
        print(f"  解析 {nm[:36]:38s} -> 未找到")

# ---- 补采评论 ----
revfile = f"{D}/v3_reviews/reviews_winners.jsonl"
revs = defaultdict(list)
if os.path.exists(revfile):
    for line in open(revfile,encoding="utf-8"):
        if not line.strip(): continue
        r=json.loads(line)
        revs[str(r.get("app_id"))].append(r.get("date") or "")

need = {aid:nm for nm,aid in resolved.items() if str(aid) not in revs}
if need:
    print(f"\n补采 {len(need)} 个赢家评论...")
    with open(revfile,"a",encoding="utf-8") as fo:
        for aid,name in need.items():
            got=0
            for page in range(1,11):
                url=f"https://itunes.apple.com/us/rss/customerreviews/page={page}/id={aid}/sortby=mostrecent/json"
                try:
                    req=urllib.request.Request(url,headers={"User-Agent":UA})
                    j=json.loads(urllib.request.urlopen(req,timeout=20).read())
                except Exception as e:
                    break
                entries=((j.get("feed") or {}).get("entry") or [])
                if not entries: break
                for e in entries:
                    if not isinstance(e,dict) or "im:rating" not in e: continue
                    def g(k):
                        v=e.get(k); return (v.get("label") if isinstance(v,dict) else v) or ""
                    fo.write(json.dumps({"review_id":str(g("id")),"app_id":str(aid),"app_name":name,
                        "title":g("title"),"body":g("content"),"stars":int(g("im:rating") or 0),
                        "version":g("im:version"),"date":g("updated")[:10],
                        "source":"apple_rss_customerreviews"},ensure_ascii=False)+"\n")
                    got+=1
                    revs[str(aid)].append(g("updated")[:10])
                time.sleep(0.25)
            print(f"    {name[:34]:36s} +{got}")

# ---- 判定 ----
def parse(s):
    if not s: return None
    try: return datetime.fromisoformat(s.replace("Z","+00:00"))
    except: return None

print("\n=== 赢家存活性(判据: 评论到达时间) ===")
print(f"{'app':38s} {'评分':>9} {'上架月':>7} {'版本停更月':>10} {'评论样本':>8} {'近12月':>7} {'近24月':>7} {'最后评论':>11} 判定")
out=[]
for nm, aid in resolved.items():
    a = pool[aid]
    rc = a.get("userRatingCount") or 0
    rel = parse(a.get("releaseDate")); upd = parse(a.get("currentVersionReleaseDate"))
    age = round((NOW-rel).days/30.44) if rel else None
    stale = round((NOW-upd).days/30.44) if upd else None
    ds=[]
    for d in revs.get(str(aid),[]):
        try: ds.append(datetime.fromisoformat(d[:10]).replace(tzinfo=timezone.utc))
        except: pass
    r12 = sum(1 for d in ds if (NOW-d).days<=365)
    r24 = sum(1 for d in ds if (NOW-d).days<=730)
    last = max(ds).strftime("%Y-%m") if ds else None
    if r12>0: v="✅活跃"
    elif r24>0: v="⚠️停滞"
    else: v="❌已死"
    out.append({"name":a.get("trackName"),"seller":a.get("sellerName"),"app_id":aid,"ratings":rc,
                "age_m":age,"stale_m":stale,"rev_samples":len(ds),"rev_12m":r12,"rev_24m":r24,
                "last_review":last,"verdict":v,"genre":a.get("primaryGenreName"),
                "price":a.get("price"),"avg":a.get("averageUserRating")})
    print(f"{str(a.get('trackName'))[:37]:38s} {rc:>9,} {str(age):>7} {str(stale):>10} {len(ds):>8} {r12:>7} {r24:>7} {str(last):>11} {v}")

act=[x for x in out if x["verdict"]=="✅活跃"]
stg=[x for x in out if x["verdict"]=="⚠️停滞"]
dead=[x for x in out if x["verdict"]=="❌已死"]
print(f"\n活跃 {len(act)} / 停滞 {len(stg)} / 已死 {len(dead)}")
if dead:
    dr=sum(x["ratings"] for x in dead); ar=sum(x["ratings"] for x in act)+sum(x["ratings"] for x in stg)
    print(f"已死组历史评分 {dr:,} ({dr/max(1,dr+ar)*100:.1f}%) —— 这些不可作为'可复制成功模式'")

json.dump({"generated":NOW.isoformat(),"all":out,"active":act,"stagnant":stg,"dead":dead,
  "criterion":"以评论到达时间判定: 近12月有新评论=活跃, 近24月=停滞, 更早=已死。版本停更仅参考。"},
  open(f"{D}/deepdive_winner_liveness.json","w"),ensure_ascii=False,indent=1)
print("\n已写入 deepdive_winner_liveness.json")
