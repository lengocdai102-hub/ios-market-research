#!/usr/bin/env python3
"""对新增池做 lookup 补全 + 相关性过滤
相关性判定: 名称/描述必须命中 房车/载具/维护/logbook/manual/checklist 等垂直语义
"""
import json, os, sys, time, urllib.request, re, collections

BASE = "/Users/maike/Desktop/iOS副业调研_2026-11-09"
D = f"{BASE}/采集数据"
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")

def lookup(ids, chunk=100):
    out = []
    for i in range(0, len(ids), chunk):
        part = ",".join(ids[i:i + chunk])
        u = f"https://itunes.apple.com/lookup?id={part}&country=us&entity=software"
        try:
            h = urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent": UA}), timeout=45).read().decode()
            out.extend(json.loads(h).get("results", []))
        except Exception as e:
            print(f"  lookup ERR {str(e)[:60]}", flush=True)
        time.sleep(0.3)
    return out

# 垂直语义词: 命中其一才算相关
RV = re.compile(r"\b(rv|motorhome|camper|caravan|trailer|boat|marine|yacht|vessel|tractor|"
                r"camping|campground|campsite|hiking|outdoor|pickup|truck|van|bus|fleet|"
                r"barn|horse|beef|dairy|farm|tractor)\b", re.I)
SERVICE = re.compile(r"\b(maintenance|maintain|service|servicing|repair|logbook|log book|"
                     r"checklist|check list|manual|inspection|inspect|tracker|record|"
                     r"warranty|schedule|scheduler|calendar|inventory|equipment|asset|"
                     r"parts|bearing|seal|propane|leveling|leveler|winteriz|towing|hitch|"
                     r"oil|filter|tire|tyre|fluid|battery|belts?|hoses?|furnace|awning|"
                     r"slide out|generator|water system|generator|anode|marine|battery bank|"
                     r"toolbox|tool kit|tool list|toolkit|garage|garage|storage|offline)\b", re.I)

def relevant(name, desc):
    b = (name or "") + " " + (desc or "")[:600]
    return bool(RV.search(b)) and bool(SERVICE.search(b))

if __name__ == "__main__":
    src = sys.argv[1]
    out_path = sys.argv[2]
    raw = json.load(open(src))
    ids = [str(r["app_id"]) for r in raw]
    print(f"待 lookup {len(ids)}", flush=True)
    meta = {}
    for i in range(0, len(ids), 100):
        part = ids[i:i + 100]
        for r in lookup(part):
            tid = str(r.get("trackId") or "")
            if tid:
                meta[tid] = r
        print(f"  {min(i+100,len(ids))}/{len(ids)} 已取 {len(meta)}", flush=True)
    json.dump(meta, open(f"{D}/_pool_new_lookup.json", "w"), ensure_ascii=False)

    keep, drop = [], []
    for r in raw:
        tid = str(r["app_id"])
        m = meta.get(tid, {})
        name = m.get("trackName") or r.get("app_name")
        desc = m.get("description") or r.get("desc") or ""
        rec = {
            "app_id": tid, "app_name": name,
            "seller": m.get("sellerName") or r.get("seller"),
            "genre": m.get("primaryGenreName") or r.get("genre"),
            "urc": m.get("userRatingCount") if m.get("userRatingCount") is not None else r.get("rating_count", 0),
            "avg": m.get("averageUserRating") or r.get("rating"),
            "price": m.get("price", r.get("price")),
            "formatted": m.get("formattedPrice"),
            "release": (m.get("releaseDate") or "")[:10],
            "cur": (m.get("currentVersionReleaseDate") or "")[:10],
            "version": m.get("version"),
            "genres": m.get("genres"),
            "file_size": m.get("fileSizeBytes"),
            "desc": desc[:400],
            "query_hit": r.get("query_hit"),
            "desc_len": len(desc),
        }
        (keep if relevant(name, desc) else drop).append(rec)
    json.dump(keep, open(out_path, "w"), ensure_ascii=False, indent=1)
    print(f"相关性过滤: 保留 {len(keep)} / 丢弃 {len(drop)}  (丢弃率 {len(drop)/max(1,len(raw))*100:.1f}%)")
    print("品类:", collections.Counter(x["genre"] for x in keep).most_common())
