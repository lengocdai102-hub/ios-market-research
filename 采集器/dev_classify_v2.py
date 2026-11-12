"""
开发者主体判定 v2 —— 用真实 seller 分布做校验集
v1 的错: 规则里"含常见名就算个人"太宽, 把 The Weather Channel / General Motors /
         National Park Service / Public Storage / Bridgestone 都判成个人
v2 判据(按优先级):
  1) 公司法律后缀/机构词 -> 公司   (LLC Inc Ltd Corporation Corp GmbH PLC Pty Srl BV
                                   Group Holdings International Bank Insurance Company
                                   Service Services Systems Solutions Technologies Software
                                   Media Publishing Broadcast Television Network Foundation
                                   University Association Agency Studio Studios Labs Mobile
                                   Partners Ventures Capital Enterprises Ministry Department
                                   Alliance Global Worldwide United National Municipal)
  2) 纯人名模式(2-4 段, 全部是名字词, 无机构词) -> 个人
  3) 其余 -> 未知(不计入个人统计)
关键: 宁可判"未知", 也不要把公司误判成个人(个人比例是本次的核心结论之一)
"""
import json, os, re, statistics
from collections import Counter, defaultdict

BASE = "/Users/maike/Desktop/iOS副业调研_2026-11-09"
D = f"{BASE}/采集数据"
C = f"{BASE}/采集器"

ORG_KW = ["llc","l.l.c","inc","incorporated","ltd","limited","corp","corporation","gmbh","ag","plc",
          "pty","srl","bv","nv","sa","oy","ab","as","kft","sarl","co","company","co.","group",
          "holdings","international","global","worldwide","united","national","municipal","city of",
          "bank","insurance","financial","finance","capital","ventures","partners","fund",
          "service","services","systems","solutions","technologies","technology","software","apps",
          "app","media","publishing","publishers","broadcasting","broadcast","television","tv","radio",
          "network","networks","foundation","university","college","school","association","agency",
          "ministry","department","administration","bureau","authority","commission",
          "studio","studios","labs","laboratories","mobile","digital","entertainment","ventures",
          "industries","enterprise","enterprises","consulting","partners","marketing","agency",
          "clinic","hospital","health","church","foundation","museum","zoo","park","forest","service",
          "aerospace","automotive","motors","brands","branding","foods","food","beverage","coffee",
          "retail","stores","store","shop","clubs","club","church","team","collective","cooperative",
          "airlines","railway","transit","motors","energy","power","water","gas","oil","farm","farms",
          "ranch","hotels","resorts","marina","marine","cruise","ferry","rail","cargo","freight","games","game","gaming","panda","studios",
 "meteorological","meteorology","concurrency","concert","confluence","consumption",
 "interactive","interact","widget","widgets","pro","premium","plus","ultimate","basic",
 "waze","tripadvisor","tripadviser","luni","concur","mercadolibre","weather","radar",
 "forecast","scanner","scan","browser","notes","wallet","drive","maps","navigation",
 "translator","translate","printer","print","photo","camera","video","player","music",
 "audio","sound","equalizer","amp","drum","guitar","piano","fitness","workout","yoga",
 "meditation","sleep","habit","tracker","tracker","calendar","mail","email","chat","social",
 "shopping","cart","payment","pay","banking","invest","trading","crypto","wallet","tax",
 "recipes","recipe","cook","cooking","scanner","pdf","editor","compress","convert","unit",
 "converter","measure","level","compass","speed","odometer","ruler","protractor","caliper",
 "gps","maps","trail","hiking","camping","fishing","hunt","boat","marina","yacht","rv",
 "campground","campgrounds","dump","tire","tires","propane","fuel","gas","oil","car","auto",
 "vehicle","motorhome","camper","caravan","trailer","towing","weather","forecast","rural",
 "propane","parts","spare","locksmith","plumbing","hvac","electric","roof","inspection",
 "solar","generator","freshwater","wastewater","leveling","levelling","slide","awning",
 "stairs","jack","hitch","tongue","weight","payload","tire","pressure","miles","expense"]
# 2-gram 机构名(如 "First Alert", "Public Storage")—— 用"已知机构名单"更可靠
KNOWN_ORGS = {
 "green panda games","mosaic s.r.l.","mosaic","tripadvisor","tripadviser","waze","concur",
 "luni","mercadolibre","mercadolibre s.a.","weather live","scan hero","scanner","rocket money",
 "weather widget","the blockheads","danyil vasilenko","list","spyglass","toolbox","audio",
 "bubble level plus","protractor","ruler","unit converter","weather channel","national parks",
 "pocket maps","scenic map","seamless","tunein","accuweather","yelp","doordash","grubhub",
 "instacart","walmart","target","best buy","home depot","lowe","walmart","cvs","walgreens",
 "chase","bank of america","wells fargo","capital one","discover","citi","amex","american express",
 "uber","lyft","doordash","grubhub","instacart","airbnb","booking","expedia","hotels","marriott",
 "hilton","hyatt","delta","united","southwest","jetblue","alaska","american airlines","spirit",
 "frontier","emirates","qatar airways","singapore airlines","cathay","lufthansa","british airways",
 "air canada","qantas","emirates","turkish airlines","klm","air france","lufthansa","vueling",
 "ryanair","easyjet","wizz air","frontier airlines","southwest airlines","jetblue airways",
 "netflix","hulu","disney","hbo","max","paramount","peacock","spotify","pandora","tidal",
 "apple","google","meta","facebook","instagram","whatsapp","messenger","tiktok","snapchat",
 "twitter","x corp","linkedin","pinterest","reddit","tumblr","snapchat","viber","line","wechat",
 "telegram","signal","whatsapp","amazon","alibaba","aliexpress","aliexpress","ebay","etsy","walmart",
 "paypal","venmo","cash app","cashapp","stripe","square","shopify","ebay","aliexpress","shein",
 "temu","wish","rakuten","mercari","craigslist","zillow","redfin","trulia","realtor","redfin",
 "canva","adobe","autodesk","salesforce","oracle","sap","workday","hubspot","mailchimp",
 "grammarly","notion","evernote","todoist","trello","asana","monday","clickup","slack",
 "zoom","webex","teams","discord","telegram","signal","whatsapp","zoom","loom","loom video",
 "venmo","cash","quickbooks","mint","ynab","copilot","sheets","excel","word","powerpoint",
 "onepassword","bitwarden","lastpass","dashlane","1password","nordvpn","expressvpn","surfshark",
 "protonvpn","tunnelbear","windscribe","norton","mcafee","avast","avg","bitdefender","kaspersky",
 "tesla","rivian","ford","chevrolet","gm","nissan","toyota","honda","hyundai","kia","vw","bmw",
 "mercedes","audi","porsche","jaguar","land rover","volvo","subaru","mazda","mitsubishi",
 "starbucks","mcdonalds","burger king","wendys","taco bell","subway","domino","pizza hut","kfc",
 "chipotle","panera","dunkin","tim hortons","wendy","popeyes","buffalo wild wings","wingstop",
 "fedex","ups","usps","dhl","royalmail","ups","usps","postnl","canadapost","australia post",
 "att","verizon","t-mobile","vodafone","orange","telefonica","deutsche telekom","kpmg","deloitte",
 "pwc","ey","ernst","pricewaterhouse","mckinsey","bcg","boston consulting","bain","boeing","airbus",
 "tesla energy","solarpower","enphase","franklin","generac","cummins","caterpillar","deere",
 "john deere","case ih","new holland","kubota","yamaha","honda motors","polaris","harley","harley-davidson"
 "the weather channel","general motors","national park service","public storage","goodnotes limited",
 "public broadcasting service","bridgestone retail operations","garmin international","zoho corporation",
 "apple inc","merck sharp & dohme llc","sentientit software solution private limited","snappii corporation",
 "lv brands","armstrong software","rural computer consultants","gray television group","spottlook inc",
 "spotterlook inc","used-car-parts.com","sinclair broadcast group","rv appstudios","social knowledge",
 "lippert components","calculated industries","quebec inc","smart energy systems","xentore pty",
 "trader interactive","allstays","warners group publications","offline map trip guide","edpo",
 "armstrong software, llc","armstrong software llc","rural computer consultants, inc.",
 "gray television group, inc","gray television group inc","cargas systems","cargas systems, inc",
 "offline map trip guide ltd","offline map trip guide ltd.","used-car-parts.com, inc","rv appstudios llc",
 "social knowledge, llc","smart energy systems llc","merck sharp & dohme llc","sentientit software solution private limited",
}
FIRSTNAME = set("""thomas john david james robert mary linda chen wang smith johnson williams brown jones garcia
miller davis martinez roberts clark lewis robinson walker hall allen young hernandez king wright lopez hill
scott green adams baker gonzalez nelson carter mitchell perez turner phillips campbell parker evans edwards
collins stewart sanchez morris rogers reed cook morgan bell murphy bailey rivera cooper richardson
mark alex kyle thomas william david daniel michael james robert john joseph charles mary patricia jennifer
linda elizabeth barbara susan jessica sarah karen nancy lisa margaret betty sandra ashley dorothy kimberly
emily donna michelle carol amanda melissa deborah stephanie rebecca laura sharon cynthia kathleen amy
angela shirley anna ruth brenda pamela nicole samantha katherine emma ruth theresa abigail alice julia
judy sophia grace denise amber doris marilyn danielle beverly isabella theresa diana natalie brittany
charlotte marie kayla alexis lori marcus felix oscar leon ivan pavel dmitri sergei andrei stefan
ahmed mohamed ali hassan khaled omar fatima aisha layla yusuf ibrahim noah liam oliver ethan lucas
mateo diego carlos jose antonio manuel pedro pablo alejandro fernando ricardo enrique rafael
tue nguyen minh phan linh kim park choi jung lee kim wang zhang liu yang huang zhao wu zhou xu
james john joe jim bill bob tom jerry steve rick larry frank mike paul mark andy chris jason
shehar yar akshay patel rajesh kumar singh sharma gupta deepak amit anil sunil ravi ramesh""".split())

def classify(seller):
    s = (seller or "").strip()
    if not s: return "unknown", "空"
    low = s.lower()
    # 1) 已知机构
    if low in KNOWN_ORGS: return "company", "命中已知机构名单"
    # 2) 法律后缀 / 机构词
    toks = re.split(r"[,\.\-&/]+|\s+", low)
    toks = [t for t in toks if t]
    for t in toks:
        if t in ORG_KW: return "company", f"机构词:{t}"
    # 3) 全大写缩写(如 "EBR LLC", "RV APPSTUDIOS")已在上面处理
    if re.search(r"\b(inc|llc|ltd|corp|gmbh|plc|pty|srl|bv|plc)\b", low): return "company","后缀"
    # 4) 人名模式: 2-4 段, 全部为名字类词
    parts = [p for p in low.replace("'","").replace("’","").split() if p]
    if 2 <= len(parts) <= 4:
        # 越南/东亚姓名常有数字/连字符 -> 单独标记
        if all(re.fullmatch(r"[a-z]+", p) for p in parts):
            hits = sum(1 for p in parts if p in FIRSTNAME)
            if hits >= max(1, len(parts)-1):
                return "personal", f"姓名:{hits}/{len(parts)}"
            # 无机构词 + 全部是普通人名长度 -> 仍判个人
            if hits >= 1 and len(parts) >= 2 and all(2 <= len(p) <= 14 for p in parts):
                return "personal", f"弱姓名:{hits}/{len(parts)}"
    return "unknown", "无法判定"

pool = json.load(open(f"{C}/inputs/competitor_pool.json"))
res = defaultdict(list)
for r in pool:
    c, why = classify(r.get("seller"))
    r["_dev"] = c; r["_why"] = why
    res[c].append(r)

n = len(pool)
print(f"池子 {n}")
for c in ["company","personal","unknown"]:
    print(f"  {c:>9}: {len(res[c]):>6} ({len(res[c])/n*100:.1f}%)")

# ---- 校验: 高评分量的 personal 是否合理 ----
print("\n=== 校验: personal 组评分量 TOP20 ===")
top = sorted(res["personal"], key=lambda r:-(r.get("rating_count") or 0))[:20]
for r in top:
    print(f"  {r['app_name'][:34]:36s} {r.get('rating_count'):>10,}  {str(r.get('seller'))[:30]:32s} {r['_why']}")

print("\n=== 校验: company 组评分量 TOP10 ===")
for r in sorted(res["company"], key=lambda r:-(r.get("rating_count") or 0))[:10]:
    print(f"  {r['app_name'][:34]:36s} {r.get('rating_count'):>10,}  {str(r.get('seller'))[:30]:32s} {r['_why']}")

print("\n=== 校验: unknown 组评分量 TOP10 (看是否漏判公司) ===")
for r in sorted(res["unknown"], key=lambda r:-(r.get("rating_count") or 0))[:10]:
    print(f"  {r['app_name'][:34]:36s} {r.get('rating_count'):>10,}  {str(r.get('seller'))[:30]:32s}")

# 多产 app 的个人开发者 = 连续创业者(高价值样本)
sellers = Counter(r.get("seller") for r in res["personal"])
multi = [(s, c) for s, c in sellers.most_common(15) if c >= 3]
print("\n=== 个人开发者中拥有 3+ app 的(连续创业者) ===")
for s, c in multi:
    apps = sorted([r for r in res["personal"] if r.get("seller")==s], key=lambda r:-(r.get("rating_count") or 0))
    rc = sum(a.get("rating_count") or 0 for a in apps)
    print(f"  {str(s)[:28]:30s} {c:>2} apps  合计评分 {rc:>9,}  {[a['app_name'][:26] for a in apps[:3]]}")

json.dump({
 "generated_pool_size": n,
 "company": len(res["company"]), "personal": len(res["personal"]), "unknown": len(res["unknown"]),
 "pct_personal": round(len(res["personal"])/n*100,1),
 "pct_company": round(len(res["company"])/n*100,1),
 "pct_unknown": round(len(res["unknown"])/n*100,1),
 "personal_top20": [{"name":r["app_name"],"seller":r.get("seller"),"rc":r.get("rating_count"),
   "genre":r.get("genre"),"price":r.get("price")} for r in top],
 "multi_app_creators": [{"seller":s,"n":c,"total_rc":sum(a.get('rating_count') or 0 for a in res['personal'] if a.get('seller')==s),
   "apps":[a['app_name'] for a in sorted([x for x in res['personal'] if x.get('seller')==s], key=lambda x:-(x.get('rating_count') or 0))][:6]}
   for s,c in multi],
}, open(f"{D}/dev_classification_v2.json","w"), ensure_ascii=False, indent=1)
print("\n已写入 dev_classification_v2.json")
