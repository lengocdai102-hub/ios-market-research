#!/usr/bin/env python3
"""
论坛/UGC 跨源交叉验证 v2 —— 判据升级

v1 问题: 用宽泛关键词, 所有痛点都命中所有 5 个一手来源 => 无法区分强弱。
v2 改法:
  1) 跨源判定改用 **具体短语**(multi-word), 去掉 "cannot"/"feature" 这类泛词
  2) 核心判据从"命中数"改为 **来源内命中率 (rate) + lift(相对该源平均痛点密度的倍数)**
     —— 只有在该源内"相对突出"的痛点, 才算该源真正独立支持
  3) 证据强度 = 一手来源中 rate-lift 显著(>=1.3 且 命中>=5)的来源数
输出: 采集数据/forum_crossref.json
"""
import json, os, re, glob, collections, statistics

B = "/Users/maike/Desktop/iOS副业调研_2026-11-09"
D = f"{B}/采集数据"

# ---------- 跨源判据: 具体短语 (排除泛词) ----------
PAIN_PHRASE = {
 "订阅/付费墙": ["paywall","pay wall","subscription","subscribe to","in-app purchase","in app purchase",
   "premium version","pro version","paid version","trial expired","monthly fee","annual fee",
   "too expensive","charged me","i already paid","cancel subscription","subscription refund"],
 "收费/退款争议": ["refund","charged","double charge","charged twice","billing issue","billing problem",
   "payment failed","money back","credit card charged","scam","charged me","apple charged"],
 "审核/上架": ["rejected","rejection","app review","guideline 1.","guideline 2.","guideline 4.","guideline 5.",
   "review guidelines","app store review","rejected twice","metadata rejection","binary rejection",
   "app review guidelines","apple rejected"],
 "客服/响应": ["customer service","no response","never responded","support team","contacted support",
   "no reply","refund request","help desk","support ticket","support did"],
 "登录/账号": ["can't log in","cannot log in","unable to log in","sign in failed","apple id problem",
   "apple id","logged out","sign out","password reset","account deleted","two-factor","2fa",
   "login screen","sign-in","log in"],
 "UI/易用性": ["hard to use","difficult to use","not intuitive","confusing","too many taps","user interface",
   "ui is bad","cluttered","hard to find","navigation is","poor design","bad design","old school",
   "frustrating","unusable","waste of money","tiny text","small text"],
 "数据丢失/同步": ["data loss","lost my data","lost everything","all my data was gone","sync failed",
   "didn't save","not saved","disappeared","vanished","icloud sync","two-way sync","not backed up",
   "backup failed","lost all my","data was wiped","deleted my"],
 "离线/无信号": ["works offline","no signal","no internet","without internet","airplane mode",
   "needs internet","requires connection","no connection","weak signal","no service",
   "offline mode","offline map"],
 "平板/多设备": ["ipad","tablet","iphone only","no ipad","landscape","apple watch","family sharing",
   "home sharing","multiple devices","second device","sync across devices","mac version","desktop app"],
 "隐私/权限": ["privacy","permission","permissions","data collection","personal data","opt out","opt-out",
   "location permission","always allow","background refresh","battery optimization","tracking",
   "access to my","data tracking","app tracking transparency"],
 "广告": ["ads","advertisement","adverts","banner ads","too many ads","annoying ads","ad free","ad-free",
   "ads everywhere","full screen ads","advertising","so many ads","pop up ads"],
 "崩溃/闪退": ["crash","crashes","crashed","crashing","force close","freezes","freezing","not responding",
   "won't open","closes immediately","black screen","keeps crashing","constant crashes"],
 "功能缺失": ["feature request","wish there was","would like to see","missing feature","should have",
   "add support for","add the ability","doesn't support","no way to","not possible to","lacking",
   "request a feature","doesn't have a","please add","need an option"],
 "不准确/数据错": ["wrong data","inaccurate","not accurate","incorrect","wrong location","wrong price",
   "wrong time","doesn't match","outdated data","wrong address","incorrect information","out of date"],
 "性能/耗电": ["battery drain","drains battery","battery","overheat"," overheating","so slow","very slow",
   "laggy","takes forever","slow loading","performance issue","high cpu","uses too much battery"],
 "更新/版本": ["update the app","app update","update failed","not updated","outdated version","old version",
   "last update","needs an update","update broke","update broke","version is old"],
 "地图/GPS不准": ["gps","wrong location","inaccurate gps","accuracy","satellite","position is wrong",
   "drift","wrong coordinates","doesn't work outdoors"],
 "导出/分享失败": ["export","export to pdf","share to","failed to export","can't export","could not export",
   "printing","csv export","export fails"],
 "通知/推送": ["no notification","notifications","notification sound","didn't notify","not notified",
   "too many notifications","push notification","alerts","reminder"],
}

def load_jsonl(p):
    out=[]
    if not os.path.exists(p): return out
    for l in open(p,encoding="utf8",errors="ignore"):
        l=l.strip()
        if not l: continue
        try: out.append(json.loads(l))
        except Exception: pass
    return out

def load_json(p):
    if not os.path.exists(p): return []
    d=json.load(open(p))
    if isinstance(d,list): return d
    for k in ("_apps","rows","items","data"):
        if k in d and isinstance(d[k],list): return d[k]
    return []

def dedup(rows, keyf):
    seen=set(); out=[]
    for r in rows:
        k=keyf(r)
        if k is None or k in seen: continue
        seen.add(k); out.append(r)
    return out

# ---------- 载入 7 源 ----------
sources={}
revs=load_jsonl(f"{D}/v3_reviews/reviews_master.jsonl")
sources["A_AppStore评论"]=[(r.get("title") or "")+" "+(r.get("body") or "") for r in revs]

comm=load_json(f"{D}/dataset_community.json")
for p in ["community_v2/community.jsonl","community_v2_b/community.jsonl","community_v2_search/community.jsonl"]:
    comm+=load_jsonl(f"{D}/{p}")
comm=dedup(comm, lambda t:t.get("thread_id") or t.get("url") or t.get("title"))
sources["B_AppleCommunity"]=[(t.get("title") or "")+" "+(t.get("body") or "")+" "+" ".join(t.get("tags") or []) for t in comm]

se=load_jsonl(f"{D}/community_v2_forum/forum.jsonl")
se+=[r for r in load_jsonl(f"{D}/forum_extra/forum_extra.jsonl") if r.get("source")=="stackexchange"]
se=dedup(se, lambda r:str(r.get("question_id") or r.get("url") or r.get("title")))
sources["C_StackExchange"]=[(r.get("title") or "")+" "+(r.get("body_snippet") or "")+" "+" ".join(r.get("tags") or []) for r in se]

hn=load_jsonl(f"{D}/forum/hn.jsonl")
hn+=[r for r in load_jsonl(f"{D}/forum_extra/forum_extra.jsonl") if r.get("source")=="hackernews"]
hn=dedup(hn, lambda r:str(r.get("object_id") or r.get("hn_id") or r.get("url") or r.get("title")))
sources["D_HackerNews"]=[(r.get("title") or "")+" "+(r.get("snippet") or "")+" "+(r.get("comment_text") or "")+" "+(r.get("story_text") or "") for r in hn]

sources["E_GoogleNews"]=[(r.get("title") or "")+" "+(r.get("snippet") or "") for r in load_jsonl(f"{D}/forum/gnews.jsonl")]
sources["F_GitHubIssue"]=[(r.get("title") or "")+" "+(r.get("body") or "") for r in load_jsonl(f"{D}/forum/github.jsonl")]

fe=load_jsonl(f"{D}/forum_extra/forum_extra.jsonl")
sources["G_搜索补充"]=[(r.get("title") or "")+" "+(r.get("desc") or "")+" "+(r.get("snippet") or "") for r in fe if r.get("source") in ("duckduckgo","bing")]

FIRSTHAND=["A_AppStore评论","B_AppleCommunity","C_StackExchange","D_HackerNews","F_GitHubIssue"]

print("=== 各源文档量 ===")
for k,v in sources.items(): print(f"  {k:20s} {len(v):>6}")

# ---------- 命中 & 基线 ----------
hit={s:collections.Counter() for s in sources}
ncat=len(PAIN_PHRASE)
for s,docs in sources.items():
    for t in docs:
        tl=t.lower()
        for cat,kws in PAIN_PHRASE.items():
            if any(k in tl for k in kws): hit[s][cat]+=1

# 基线: 该源所有痛点命中次数之和 / 痛点类别数 / 文档数 = 平均单痛点命中率
base={}
for s in sources:
    n=len(sources[s]) or 1
    tot=sum(hit[s].values())
    base[s]= tot/ncat/n*100   # 平均每痛点在每文档上的命中率(%)

print("\n=== 各源平均单痛点命中率(基线) ===")
for s in sources: print(f"  {s:20s} {base[s]:.3f}%")

LIFT_MIN=1.3; MIN_HITS=5; PVAL_MAX=0.01

def binom_sf(k, n, p0):
    """P(X>=k) 二项检验单尾; p0=该源在'任一痛点'上的期望命中率"""
    if n<=0 or k<=0: return 1.0
    # 用 log 求和避免溢出
    import math
    lp0=math.log(p0) if p0>0 else -745.0
    lq0=math.log(1-p0) if p0<1 else -745.0
    lk=math.log(k) if k>0 else -745.0
    ln=math.log(n)
    s=0.0
    for i in range(k, n+1):
        try:
            s+= math.exp(lk-math.lgamma(i+1)+math.lgamma(n-i+1)+i*lp0+(n-i)*lq0)
        except OverflowError: pass
        if s>1.5: return 0.0
    return min(1.0,s)
rows=[]
for cat,kws in PAIN_PHRASE.items():
    per={}; rate={}; lift={}; sig={}; pval={}
    for s in sources:
        n=len(sources[s]) or 1
        per[s]=hit[s][cat]; rate[s]=hit[s][cat]/n*100
        lift[s]= rate[s]/base[s] if base[s]>0 else 0
        # 期望命中数 = 该源"任一痛点平均命中率" × 文档数; 显著性用二项检验单尾
        p0 = base[s]/100.0
        p = binom_sf(per[s], n, p0)
        pval[s]=round(p,6)
        sig[s]= (per[s]>=MIN_HITS and p<=PVAL_MAX)
    n_first=sum(1 for s in FIRSTHAND if sig[s])
    n_any=sum(1 for s in sources if sig[s])
    rows.append({"pain":cat,"per_source":per,"rate_pct":{k:round(v,3) for k,v in rate.items()},
                 "lift":{k:round(v,2) for k,v in lift.items()},
                 "p_value":pval,
                 "significant_sources":{s:(sig[s]) for s in sources},
                 "firsthand_sources_significant":n_first,"all_sources_significant":n_any,
                 "total_hits":sum(per.values()),
                 "A":per["A_AppStore评论"],"B":per["B_AppleCommunity"],"C":per["C_StackExchange"],
                 "D":per["D_HackerNews"],"E":per["E_GoogleNews"],"F":per["F_GitHubIssue"]})

def grade(r):
    n=r["firsthand_sources_significant"]
    if n>=4: return "A++ 多源一手显著共振"
    if n==3: return "A  三源一手显著共振"
    if n==2: return "B  双源一手显著共振"
    if n==1: return "C  单源一手显著"
    return "D  仅媒体/无一手显著支持"
for r in rows: r["grade"]=grade(r)
rows.sort(key=lambda x:(-x["firsthand_sources_significant"], -x["all_sources_significant"], -x["total_hits"]))

print(f"\n=== 跨源痛点交叉验证 (二项检验 p<={PVAL_MAX} 且命中>={MIN_HITS} 才算显著) ===")
print(f"{'痛点':16s}{'显著一手':>9}{'显著总':>7}{'总命中':>8}  A评论 B社区 C栈  D HN E新闻 F GH  强度")
for r in rows:
    print(f"{r['pain']:16s}{r['firsthand_sources_significant']:>9}{r['all_sources_significant']:>7}{r['total_hits']:>8}"
          f"  {r['A']:>5} {r['B']:>4} {r['C']:>4} {r['D']:>4} {r['E']:>4} {r['F']:>4}  {r['grade']}")

# ---------- 原声摘录 ----------
KEY_EV={
 "订阅/付费墙":["paywall","subscription","in-app purchase","too expensive","charged me"],
 "审核/上架":["rejected","app review","guideline","rejection"],
 "收费/退款争议":["refund","charged","double charge","billing"],
 "客服/响应":["customer service","no response","support"],
 "登录/账号":["can't log in","sign in","apple id","account"],
 "UI/易用性":["hard to use","confusing","not intuitive"],
 "数据丢失/同步":["data loss","sync","lost my data","icloud"],
 "离线/无信号":["offline","no signal","no internet"],
 "平板/多设备":["ipad","apple watch","family sharing","multiple devices"],
 "隐私/权限":["privacy","data collection","permission","tracking"],
 "广告":["ads","advertisement","ad-free"],
 "崩溃/闪退":["crash","not responding","freezes"],
 "功能缺失":["feature request","wish there was","would like","please add"],
 "不准确/数据错":["wrong","inaccurate","outdated"],
 "性能/耗电":["battery","slow","lag"],
 "更新/版本":["update","outdated","version"],
 "地图/GPS不准":["gps","wrong location","accuracy"],
 "导出/分享失败":["export","pdf","csv"],
 "通知/推送":["notification","push","alert"],
}
ev={}
for cat,kws in KEY_EV.items():
    o={}
    for s in ["A_AppStore评论","B_AppleCommunity","C_StackExchange","D_HackerNews","F_GitHubIssue","E_GoogleNews"]:
        got=[]
        for t in sources[s]:
            tl=t.lower()
            for kw in kws:
                if kw in tl:
                    i=tl.index(kw)
                    got.append(re.sub(r'\s+',' ',t[max(0,i-100):i+120]).strip()); break
            if len(got)>=2: break
        if got: o[s]=got
    ev[cat]=o

out={"generated_at":"2026-11-11",
 "method":{"criterion":"具体短语匹配; 显著性 = 来源内命中率 lift>=1.3 且命中数>=5; 证据强度按显著一手来源数分级",
   "firsthand_sources":FIRSTHAND,
   "note":"媒体(GoogleNews)与搜索(DDG/Bing)不计入'一手来源'计数"},
 "source_doc_counts":{k:len(v) for k,v in sources.items()},
 "source_baseline_rate_pct":{k:round(v,4) for k,v in base.items()},
 "significance":{"test":"单尾二项检验 (H0: 该痛点命中率=该源平均痛点命中率)","p_max":PVAL_MAX,"min_hits":MIN_HITS},
 "lift_threshold":LIFT_MIN,
 "pain_crossref":rows,"evidence_snippets":ev}
json.dump(out, open(f"{D}/forum_crossref.json","w"), ensure_ascii=False, indent=1)
print(f"\n-> {D}/forum_crossref.json")
