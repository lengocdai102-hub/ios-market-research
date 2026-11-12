"""
深挖 I: 895 竞品池的赢家模式分析
问题: 独立开发者能不能赢? 赢的话赢在什么模式上?
方法:
  1) 按开发主体(个人 vs 公司)对比 评分量分布 —— 独立开发者到底能不能拿到量
  2) 按"是否一次性买断"对比 —— 定价模式是否是胜负手
  3) 按"是否有 IAP"对比 —— 变现模式
  4) 找出所有评分量 >1000 的个人开发者 app —— 他们做对了什么
  5) 按上架时长标准化, 比较同存活期的成功率
"""
import json, os, re, datetime, statistics
from collections import Counter, defaultdict

BASE = "/Users/maike/Desktop/iOS副业调研_2026-11-09"
D = f"{BASE}/采集数据"
NOW = datetime.date(2026, 11, 10)

pool = json.load(open(f"{D}/_expanded_competitors.json"))
vals = list(pool.values())
iap = json.load(open(f"{D}/iap_prices_expanded.json"))["_apps"]

def seller_type(s):
    s = str(s or "").strip()
    if not s: return "未知"
    if re.match(r'^[A-Z][a-zA-Z]+ [A-Z][a-zA-Z]+$', s) and len(s.split()) in (2,3):
        if any(k in s.lower() for k in ["llc","inc","ltd","corp","gmbh","plc","co","company","group","labs","studios","technologies","software","systems","solutions","media","publishing","digital","holdings","ventures","capital","partners","associates","clinic","university","national","state","department","agency","service","services"]):
            return "公司主体"
        return "个人开发者"
    if any(k in s.lower() for k in ["llc","inc","ltd","corp","gmbh","plc","company","group","labs","studios","technologies","software","systems","solutions","media","publishing","digital","holdings","ventures","capital","partners","associates","center","centre","co."]):
        return "公司主体"
    if re.match(r'^[A-Z][a-z]+ [A-Z][a-z]+$', s):
        return "个人开发者"
    return "其他/未识别"

def months_alive(x):
    r = x.get("releaseDate")
    if not r: return None
    try:
        return round((NOW - datetime.date.fromisoformat(r[:10])).days / 30.4, 1)
    except Exception:
        return None

def has_lifetime(x):
    blob = ((x.get("trackName") or "") + " " + (x.get("description") or "") + " " + str(x.get("price") or "")).lower()
    return any(k in blob for k in ["lifetime", "one-time", "one time purchase", "pay once", "no subscription", "one-time payment", "permanent"])

def get_iap(x):
    a = iap.get(str(x.get("trackId") or x.get("app_id") or ""))
    return a if a else {}

for x in vals:
    x["_stype"] = seller_type(x.get("sellerName"))
    x["_rc"] = x.get("userRatingCount") or 0
    x["_m"] = months_alive(x)
    x["_life"] = has_lifetime(x)
    ia = get_iap(x)
    x["_has_iap"] = bool(ia.get("iap_prices"))
    x["_iap_min"] = ia.get("iap_min")
    x["_iap_med"] = ia.get("iap_median")

print("=" * 100)
print(f"【深挖I】895 竞品池 · 赢家模式分析")
print("=" * 100)
print(f"池子总数 {len(vals)}")

print("\n【1】开发主体对比")
for st in ["公司主体", "个人开发者", "其他/未识别", "未知"]:
    g = [x for x in vals if x["_stype"] == st]
    if not g: continue
    rc = sorted(x["_rc"] for x in g)
    tot = sum(rc)
    print(f"  {st:<12} {len(g):>4} app ({len(g)/len(vals)*100:>5.1f}%)  "
          f"评分合计 {tot:>9,} ({tot/sum(x['_rc'] for x in vals)*100:>5.1f}%)  "
          f"中位评分 {rc[len(rc)//2]:>6}  最大 {max(rc):>8,}  "
          f"零评分 {sum(1 for x in g if x['_rc']==0):>4} ({sum(1 for x in g if x['_rc']==0)/len(g)*100:.0f}%)")

print("\n【2】定价模式对比 (一次性买断 vs 纯订阅/IAP)")
for lab, f in [("一次性买断(描述含lifetime/one-time)", lambda x: x["_life"]),
               ("有 IAP", lambda x: x["_has_iap"]),
               ("两者都有", lambda x: x["_life"] and x["_has_iap"]),
               ("纯免费(无IAP且price=0)", lambda x: (not x["_has_iap"]) and (x.get("price") or 0) == 0),
               ("一次性付费(price>0)", lambda x: (x.get("price") or 0) > 0)]:
    g = [x for x in vals if f(x)]
    if not g: continue
    rc = sorted(x["_rc"] for x in g)
    med = rc[len(rc)//2]
    hit100 = sum(1 for x in g if x["_rc"] >= 100)
    print(f"  {lab:<34} {len(g):>4} app  中位评分 {med:>6}  最大 {max(rc):>8,}  "
          f"评分≥100 的占 {hit100/len(g)*100:>5.1f}%")

print("\n【3】同等存活期对比 (标准化, 排除上架时长差异)")
buckets = [(0,6),(6,12),(12,24),(24,48),(48,999)]
print(f"  {'存活区间':<12} {'公司主体':>22} {'个人开发者':>22} {'个人胜率':>9}")
print(f"  {'':<12} {'app数/中位评分/≥100占比':>22} {'app数/中位评分/≥100占比':>22}")
for lo, hi in buckets:
    line = f"  {f'{lo}-{hi}月':<12}"
    res = {}
    for st in ["公司主体", "个人开发者"]:
        g = [x for x in vals if x["_stype"] == st and x["_m"] is not None and lo <= x["_m"] < hi]
        if not g:
            res[st] = None; line += f" {'-':>22}"; continue
        rc = sorted(x["_rc"] for x in g)
        med = rc[len(rc)//2]
        h100 = sum(1 for x in g if x["_rc"] >= 100) / len(g) * 100
        res[st] = (len(g), med, h100)
        line += f" {f'{len(g)}/{med}/{h100:.0f}%':>22}"
    if res["公司主体"] and res["个人开发者"]:
        cg, pg = res["公司主体"], res["个人开发者"]
        win = pg[1] / cg[1] if cg[1] else 0
        line += f" {f'{win:.2f}x':>9}"
    print(line)

print("\n【4】所有 评分量>1000 的个人开发者 app (他们做对了什么)")
pers = sorted([x for x in vals if x["_stype"] == "个人开发者" and x["_rc"] > 1000],
               key=lambda x: -x["_rc"])
print(f"  共 {len(pers)} 个")
for x in pers[:20]:
    print(f"    {x['trackName'][:40]:42} 评分={x['_rc']:>7}  均分={x.get('averageUserRating')}  "
          f"存活={x['_m']}月  买断={x['_life']}  IAP最小={x['_iap_min']}  {x.get('primaryGenreName')}")
if pers:
    withiap = sum(1 for x in pers if x["_has_iap"])
    withlife = sum(1 for x in pers if x["_life"])
    print(f"\n    其中: 有IAP {withiap}/{len(pers)} ({withiap/len(pers)*100:.0f}%)   一次买断 {withlife}/{len(pers)} ({withlife/len(pers)*100:.0f}%)")

print("\n【5】个人开发者 评分量 TOP20 全表")
allpers = sorted([x for x in vals if x["_stype"] == "个人开发者"], key=lambda x: -x["_rc"])
print(f"  个人开发者共 {len(allpers)} 个, 其中零评分 {sum(1 for x in allpers if x['_rc']==0)} ({sum(1 for x in allpers if x['_rc']==0)/len(allpers)*100:.0f}%)")
print(f"  评分≥100: {sum(1 for x in allpers if x['_rc']>=100)} ({sum(1 for x in allpers if x['_rc']>=100)/len(allpers)*100:.0f}%)")
for x in allpers[:20]:
    print(f"    {x['trackName'][:38]:40} 评分={x['_rc']:>7}  存活={str(x['_m']):>6}月  买断={x['_life']}  IAP={x['_iap_min']}")

print("\n【6】公司主体 vs 个人开发者 的评分量集中度 (基尼式简单对比)")
for st in ["公司主体", "个人开发者"]:
    g = sorted((x["_rc"] for x in vals if x["_stype"] == st), reverse=True)
    if not g: continue
    tot = sum(g)
    top10 = sum(g[:10]) / tot * 100 if tot else 0
    print(f"  {st:<12} app={len(g):>4}  Top10 占其评分总量 {top10:>5.1f}%   中位 {g[len(g)//2]:>5}  均值 {tot/len(g):>8.1f}")

json.dump({"pool_size": len(vals),
           "by_seller": {st: {"apps": len([x for x in vals if x["_stype"]==st]),
                               "ratings_total": sum(x["_rc"] for x in vals if x["_stype"]==st),
                               "median": statistics.median([x["_rc"] for x in vals if x["_stype"]==st]),
                               "max": max([x["_rc"] for x in vals if x["_stype"]==st]),
                               "zero": sum(1 for x in vals if x["_stype"]==st and x["_rc"]==0)}
                        for st in ["公司主体","个人开发者","其他/未识别","未知"]},
           "pers_top": [{"name": x["trackName"], "rc": x["_rc"], "months": x["_m"],
                         "lifetime": x["_life"], "iap_min": x['_iap_min'],
                         "genre": x.get("primaryGenreName"), "seller": x.get("sellerName")}
                        for x in allpers[:60]],
           "pers_winners": [{"name": x["trackName"], "rc": x["_rc"], "months": x["_m"],
                             "lifetime": x["_life"], "iap_min": x['_iap_min'],
                             "genre": x.get("primaryGenreName"), "seller": x.get("sellerName")}
                            for x in pers]},
          open(f"{D}/deepdive_winner_patterns.json", "w"), ensure_ascii=False, indent=2)
print(f"\n  -> {D}/deepdive_winner_patterns.json")
