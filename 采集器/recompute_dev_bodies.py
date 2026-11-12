"""
重算 §4.1 开发主体对比 (10,312 池, 用 dev_classify_v2 的判定)
输出: dev_body_comparison.json
"""
import json, os, statistics
from collections import Counter

BASE="/Users/maike/Desktop/iOS副业调研_2026-11-09"
D=f"{BASE}/采集数据"
C=f"{BASE}/采集器"
pool=json.load(open(f"{C}/inputs/competitor_pool.json"))
if isinstance(pool, list):
    pool = {str(a.get("app_id") or i): a for i,a in enumerate(pool)}

dev=json.load(open(f"{D}/dev_classification_v2.json"))

# dev_classify_v2 的判定逻辑复刻
import importlib.util
spec=importlib.util.spec_from_file_location("dc", f"{C}/dev_classify_v2.py")
# 不直接 import(会执行), 改为读它导出的逐 app 分类
cls=None
if cls is None:
    print("没有逐app分类文件, 改为重新跑 dev_classify_v2 的分类函数")
    # 从脚本里提取 classify 函数
    src=open(f"{C}/dev_classify_v2.py").read()
    ns={}
    # 截取到 "if __name__" 之前
    head=src.split('if __name__')[0]
    exec(compile(head, "dev_classify_v2", "exec"), ns)
    fn_cls = ns.get("classify") or ns.get("classify_seller")
    print("找到函数:", fn_cls)
    cls={}
    for aid,a in pool.items():
        seller=a.get("seller") or ""
        r=fn_cls(seller)
        cls[aid] = r[0] if isinstance(r,(tuple,list)) else r

rows=[]
for aid,a in pool.items():
    rc=a.get("rating_count") or a.get("userRatingCount") or 0
    rows.append({"aid":aid,"name":a.get("app_name"),"seller":a.get("seller"),
                 "rc":rc,"rating":a.get("rating"),"cls":cls.get(aid) or cls.get(str(aid))})
json.dump(rows, open(f"{D}/dev_classification_apps.json","w"), ensure_ascii=False)

groups={}
for r in rows:
    groups.setdefault(r["cls"],[]).append(r)

out={}
print(f"\n{'主体':10s} {'app数':>7} {'占比':>7} {'评分合计':>14} {'占比':>7} {'中位评分':>9} {'最大':>10} {'零评分率':>8}")
total_rc=sum(r["rc"] for r in rows)
for g,rs in sorted(groups.items(), key=lambda z:-len(z[1])):
    rcs=[r["rc"] for r in rs]
    zero=sum(1 for x in rcs if x==0)
    out[g]={"apps":len(rs),"pct_apps":round(len(rs)/len(rows)*100,1),
            "rating_sum":sum(rcs),"pct_rating":round(sum(rcs)/total_rc*100,1) if total_rc else 0,
            "median_rating":int(statistics.median(rcs)),"max":max(rcs),
            "zero_pct":round(zero/len(rs)*100,1)}
    print(f"{str(g):10s} {len(rs):>7,} {len(rs)/len(rows)*100:>6.1f}% {sum(rcs):>14,} "
          f"{sum(rcs)/total_rc*100:>6.1f}% {int(statistics.median(rcs)):>9,} {max(rcs):>10,} {zero/len(rs)*100:>7.1f}%")

# 个人开发者 TOP15
pers=sorted(groups.get("personal",[]), key=lambda z:-z["rc"])[:15]
out["personal_top15"]=[{"name":r["name"],"seller":r["seller"],"rc":r["rc"]} for r in pers]
print("\n=== 个人开发者评分量 TOP15 ===")
for r in pers: print(f"  {str(r['name'])[:40]:42s} {r['seller'][:24]:26s} {r['rc']:>8,}")

json.dump(out, open(f"{D}/dev_body_comparison.json","w"), ensure_ascii=False, indent=1)
print("\n已写入 dev_body_comparison.json")
