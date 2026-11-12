"""
深挖 L: 连续创业者模式验证 (核心论据)
发现: Tue Nguyen Minh 一个人 7 个 app 合计 85,408 评分, 且全是单功能小工具
      Kyle Modesitt 7 个 app 合计 15,788 评分, 全是 RV/露营独占数据
这两个人的 app 组合, 是"可复制模式"的最强证据 —— 比任何"共性统计"都硬
方法: 对每个拥有 3+ app 的个人开发者, 拉全部 app 的评论, 逐个验证:
      1) 是否仍活跃(评论到达时间)
      2) 功能是否极窄(标题词数 / 品类)
      3) 变现方式
输出: 可复制的"个人开发者路径模板"
"""
import json, os, urllib.request, time, statistics
from collections import defaultdict
from datetime import datetime, timezone

BASE = "/Users/maike/Desktop/iOS副业调研_2026-11-09"
D = f"{BASE}/采集数据"
C = f"{BASE}/采集器"
NOW = datetime(2026, 11, 10, tzinfo=timezone.utc)
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/131.0.0.0 Safari/537.36"

dc = json.load(open(f"{D}/dev_classification_v2.json"))
pool = json.load(open(f"{C}/inputs/competitor_pool.json"))
bym = {}
for r in pool: bym[str(r.get("app_id"))] = r

creators = dc["multi_app_creators"]
print(f"拥有 3+ app 的个人开发者: {len(creators)} 个\n")

revfile = f"{D}/v3_reviews/reviews_creators.jsonl"
revs = defaultdict(list)
if os.path.exists(revfile):
    for line in open(revfile,encoding="utf-8"):
        if not line.strip(): continue
        r=json.loads(line); revs[str(r.get("app_id"))].append(r.get("date") or "")

# 需要补采评论的 app
need = []
for c in creators:
    for nm in c["apps"]:
        for r in pool:
            if r.get("app_name")==nm:
                if str(r.get("app_id")) not in revs: need.append((str(r.get("app_id")), nm))
                break
if need:
    print(f"补采 {len(need)} 个 app 评论...")
    with open(revfile,"a",encoding="utf-8") as fo:
        for aid,name in need:
            got=0
            for page in range(1,6):
                url=f"https://itunes.apple.com/us/rss/customerreviews/page={page}/id={aid}/sortby=mostrecent/json"
                try:
                    req=urllib.request.Request(url,headers={"User-Agent":UA})
                    j=json.loads(urllib.request.urlopen(req,timeout=20).read())
                except: break
                entries=((j.get("feed") or {}).get("entry") or [])
                if not entries: break
                for e in entries:
                    if not isinstance(e,dict) or "im:rating" not in e: continue
                    def g(k):
                        v=e.get(k); return (v.get("label") if isinstance(v,dict) else v) or ""
                    fo.write(json.dumps({"review_id":str(g("id")),"app_id":aid,"app_name":name,
                        "body":g("content"),"stars":int(g("im:rating") or 0),
                        "date":g("updated")[:10],"version":g("im:version")},ensure_ascii=False)+"\n")
                    got+=1; revs[aid].append(g("updated")[:10])
                time.sleep(0.2)
            if got: print(f"    {name[:36]:38s} +{got}")

print(f"\n=== 连续创业者明细 ===")
print(f"{'开发者':22s} {'app数':>4} {'合计评分':>10} {'活跃app':>8} {'总评论样本':>10} {'近12月评论':>11}  品类")
rows=[]
for c in creators:
    detail=[]
    act=0; r12=0; rtot=0
    for r in pool:
        if r.get("seller")!=c["seller"]: continue
        aid=str(r.get("app_id")); rc=r.get("rating_count") or 0
        ds=[]
        for d in revs.get(aid,[]):
            try: ds.append(datetime.fromisoformat(d[:10]).replace(tzinfo=timezone.utc))
            except: pass
        n12=sum(1 for d in ds if (NOW-d).days<=365)
        alive = n12>0
        if alive: act+=1
        r12+=n12; rtot+=len(ds)
        detail.append({"name":r.get("app_name"),"rc":rc,"genre":r.get("genre"),"price":r.get("price"),
                       "alive":alive,"rev_samples":len(ds),"rev_12m":n12,
                       "last":max(ds).strftime("%Y-%m") if ds else None})
    genres = sorted(set(d["genre"] for d in detail if d["genre"]))
    rows.append({"seller":c["seller"],"n":len(detail),"total_rc":c["total_rc"],"alive":act,
                 "rev_samples":rtot,"rev_12m":r12,"genres":genres,"apps":detail})
    print(f"{c['seller'][:21]:22s} {len(detail):>4} {c['total_rc']:>10,} {act:>8} {rtot:>10} {r12:>11}  {', '.join(g[:12] for g in genres)}")

rows.sort(key=lambda x:-x["total_rc"])
print("\n=== TOP5 连续创业者逐 app 明细 ===")
for c in rows[:5]:
    print(f"\n● {c['seller']}  ({c['n']} apps, 合计 {c['total_rc']:,} 评分, {c['alive']} 个仍活跃)")
    for d in sorted(c["apps"], key=lambda x:-(x["rc"] or 0)):
        st = "✅活跃" if d["alive"] else ("—" if d["rev_samples"]==0 else "❌")
        print(f"    {d['name'][:38]:40s} rc={d['rc']:>8,} 均品类={str(d['genre'])[:13]:14s} 买断=${d['price'] or 0:>6.2f} 评论{d['rev_samples']:>4} 近12月{d['rev_12m']:>3} {st}")

# ---- 提炼: 连续创业者的共同特征 ----
print("\n=== 连续创业者特征提炼 ===")
active_rows=[c for c in rows if c["alive"]>0]
if active_rows:
    print(f"  有 app 仍活跃的连续创业者: {len(active_rows)}/{len(rows)}")
    tot_apps=sum(c["n"] for c in active_rows)
    tot_alive=sum(c["alive"] for c in active_rows)
    print(f"  他们的 app: {tot_apps} 个, 其中 {tot_alive} 个仍活跃 ({tot_alive/tot_apps*100:.0f}%)")
    # 窄功能判定
    narrow=[d for c in active_rows for d in c["apps"] if d["alive"]]
    print(f"  仍活跃的 app 分类分布:")
    from collections import Counter
    cc=Counter(d["genre"] for d in narrow)
    for g,n in cc.most_common(10): print(f"    {str(g)[:24]:26s} {n}")
    # 变现
    paid=[d for d in narrow if (d["price"] or 0)>0]
    print(f"  变现: 买断 {len(paid)}/{len(narrow)} ({len(paid)/len(narrow)*100:.0f}%), 全部免费 {len(narrow)-len(paid)}")

json.dump({"generated":NOW.isoformat(),"creators":rows,
 "n_creators":len(rows),"n_active_creators":len(active_rows)},
 open(f"{D}/deepdive_serial_entrepreneurs.json","w"),ensure_ascii=False,indent=1)
print("\n已写入 deepdive_serial_entrepreneurs.json")
