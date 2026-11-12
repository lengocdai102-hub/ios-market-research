"""补采关键赢家的评论, 用于独立判定"是否已死"""
import json, os, urllib.request, time, sys
from datetime import datetime, timezone

D = "/Users/maike/Desktop/iOS副业调研_2026-11-09/采集数据"
NOW = datetime(2026,11,10,tzinfo=timezone.utc)

TARGETS = [
    ("571626623","Lists To do"), ("425589565","GPS Tracks"), ("318095638","Errands To-Do List"),
    ("1169702883","Boondocking"), ("1096754487","RV Dump Stations"), ("1125904118","USFS & BLM Campgrounds"),
    ("573350489","Bubble Level 2022"), ("460724675","Speedometer 55 GPS Speed & HUD"),
    ("1145180340","Fishing Knots FishPlanet"), ("1099026886","Packr Travel Packing List"),
    ("1214997749","MapChart App"), ("1497566325","Guru Maps"), ("1479512308","Vehicle Maintenance Tracker"),
    ("1146436765","Checklist – Simple Task Lists"), ("1544731908","Lists To do New"),
]
UA="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/131.0.0.0 Safari/537.36"
out=f"{D}/v3_reviews/reviews_winners.jsonl"
n=0
with open(out,"w",encoding="utf-8") as fo:
    for aid,name in TARGETS:
        got=0; last=None
        for page in range(1,11):
            url=f"https://itunes.apple.com/us/rss/customerreviews/page={page}/id={aid}/sortby=mostrecent/json"
            try:
                req=urllib.request.Request(url,headers={"User-Agent":UA})
                j=json.loads(urllib.request.urlopen(req,timeout=20).read())
            except Exception as e:
                print(f"  {name}: page{page} ERR {e}"); break
            entries=((j.get("feed") or {}).get("entry") or [])
            if not entries: break
            for e in entries:
                if not isinstance(e,dict) or "im:rating" not in e: continue
                def g(k):
                    v=e.get(k)
                    return (v.get("label") if isinstance(v,dict) else v) or ""
                fo.write(json.dumps({"review_id":str(g("id")),"app_id":str(aid),"app_name":name,
                    "title":g("title"),"body":g("content"),"stars":int(g("im:rating") or 0),
                    "version":g("im:version"),"date":g("updated")[:10],
                    "vote_sum":g("im:voteSum"),"vote_count":g("im:voteCount"),
                    "author":g("author"),"source":"apple_rss_customerreviews"},ensure_ascii=False)+"\n")
                got+=1; n+=1
                d=g("updated")[:10]
                if d: last=max(last or d, d)
            time.sleep(0.3)
        print(f"  {name[:34]:36s} {got:>4} 条  最后评论 {last}")
json.dump({aid:name for aid,name in TARGETS},open(f"{D}/_winner_targets.json","w"),ensure_ascii=False)
print("合计",n,"条 →",out)
