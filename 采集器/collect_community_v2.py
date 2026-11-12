"""
Apple Community 深度采集器 v2
- 板块页 /community/<board>?page=N，标题选择器 a.content-post-title
- 搜索页 /search?q=...&page=N，标题选择器 a.thread-title
- 单帖抓取 .post-content 正文片段 + 发帖时间 + 回复数
- 全部字段：来源URL、采集时间、板块、标题、正文片段
- 支持 --only-boards 限制板块（用于并行分片），--qfile 搜索词
"""
import json, os, re, sys, time, urllib.parse, argparse
from datetime import datetime, timezone
from patchright.sync_api import sync_playwright

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36")

ALL_BOARDS = {
    "iphone": "iPhone", "macos": "macOS", "mac": "Mac", "ipad": "iPad",
    "watch": "Watch", "apple-vision-pro": "Vision Pro",
    "apple-intelligence": "Apple Intelligence",
    "applications-services": "Applications & Services",
    "apple-account": "Apple Account", "icloud": "iCloud", "music": "Music",
    "airpods": "AirPods", "accessories": "Accessories",
    "tv-and-home": "TV & Home", "stores": "Stores",
    "using_apple_support_communities": "Using Apple Support Communities",
    "wallet/other-apple-wallet": "Wallet",
    "macos-tv-home-theater": "TV & Home Theater",
}


def log(m):
    print(m, flush=True)


def now_iso():
    return datetime.now(timezone.utc).isoformat()


class Collector:
    def __init__(self, delay=1.5, pages=3):
        self.delay = delay
        self.pages = pages
        self.rows = []
        self.seen = set()

    def _norm(self, t):
        return re.sub(r"\s+", " ", (t or "").strip())

    def scrape_list(self, pg, url, retries=3):
        last = None
        for att in range(retries):
            try:
                pg.goto(url, wait_until="domcontentloaded", timeout=45000)
                pg.wait_for_selector("a[href*='/thread/']", timeout=15000)
                pg.wait_for_timeout(700)
                out = []
                for sel in ("a.thread-title[href*='/thread/']",
                            "a.content-post-title[href*='/thread/']"):
                    els = pg.query_selector_all(sel)
                    if not els:
                        continue
                    for e in els:
                        href = e.get_attribute("href") or ""
                        if "?answerId=" in href or "#" in href:
                            continue
                        if not re.match(r"^/thread/\d+", href):
                            continue
                        title = self._norm(e.inner_text())
                        if title:
                            out.append((href, title))
                    if out:
                        break
                if out:
                    return out
                last = "no items"
            except Exception as e:
                last = f"{type(e).__name__} {str(e)[:60]}"
                time.sleep(2.5)
        log(f"  ! list fail {url}: {last}")
        return []

    def scrape_detail(self, pg, href, title, board):
        url = "https://discussions.apple.com" + href
        try:
            pg.goto(url, wait_until="domcontentloaded", timeout=45000)
            pg.wait_for_selector(".post-content", timeout=20000)
        except Exception as e:
            log(f"  ! detail fail {href}: {type(e).__name__} {str(e)[:50]}")
            return None
        pg.wait_for_timeout(300)
        body_snippet, posted = "", ""
        pcs = pg.query_selector_all(".post-content")
        if pcs:
            txt = pcs[0].inner_text() or ""
            keep = []
            for l in [x.strip() for x in txt.split("\n") if x.strip()]:
                if l.startswith("Posted on"):
                    posted = l.replace("Posted on", "").strip()
                    continue
                if re.fullmatch(r"[0-9★☆]+", l) or l in ("Reply", "Me too", "Share"):
                    continue
                keep.append(l)
            body_snippet = " ".join(keep).strip()
        if not posted:
            el = pg.query_selector("time, .timestamp-published")
            if el:
                posted = (el.inner_text() or "").strip()
        replies = 0
        m = re.search(r"(\d+)\s+repl", pg.inner_text("body"))
        if m:
            replies = int(m.group(1))
        return {
            "board": board,
            "title": title,
            "url": url,
            "thread_id": href.split("/")[-1],
            "body_snippet": body_snippet[:600],
            "body_len": len(body_snippet),
            "posted": posted,
            "replies": replies,
            "collected_at": now_iso(),
        }

    def run(self, out_dir, mode="both", qfile=None, only_boards=None):
        os.makedirs(out_dir, exist_ok=True)
        path = os.path.join(out_dir, "community.jsonl")
        fh = open(path, "a", encoding="utf-8")
        boards = ALL_BOARDS
        if only_boards:
            boards = {k: v for k, v in ALL_BOARDS.items() if k in only_boards}
        with sync_playwright() as p:
            br = p.chromium.launch(channel="chrome", headless=True)
            ctx = br.new_context(user_agent=UA, locale="en-US",
                                 viewport={"width": 1512, "height": 1400})
            pg = ctx.new_page()

            if mode in ("both", "boards"):
                for slug, label in boards.items():
                    got = 0
                    for pi in range(1, self.pages + 1):
                        items = self.scrape_list(
                            pg, f"https://discussions.apple.com/community/{slug}?page={pi}")
                        if not items:
                            break
                        for href, title in items:
                            if href in self.seen:
                                continue
                            self.seen.add(href)
                            d = self.scrape_detail(pg, href, title, label)
                            if d:
                                fh.write(json.dumps(d, ensure_ascii=False) + "\n")
                                fh.flush()
                                self.rows.append(d)
                                got += 1
                        time.sleep(self.delay)
                    log(f"[board] {label:38} {got:3} new, total {len(self.rows)}")

            if mode in ("both", "search") and qfile:
                queries = json.load(open(qfile))
                for q in queries:
                    for pi in range(1, self.pages + 1):
                        url = ("https://discussions.apple.com/search?q="
                               + urllib.parse.quote(q) + f"&page={pi}")
                        items = self.scrape_list(pg, url)
                        if not items:
                            break
                        new = 0
                        for href, title in items:
                            if href in self.seen:
                                continue
                            self.seen.add(href)
                            new += 1
                            d = self.scrape_detail(pg, href, title, "")
                            if d:
                                d["query"] = q
                                fh.write(json.dumps(d, ensure_ascii=False) + "\n")
                                fh.flush()
                                self.rows.append(d)
                            time.sleep(self.delay)
                        log(f"[search] {q[:40]:42} p{pi} {len(items):3} (new {new:2}) total {len(self.rows)}")
                        if new == 0 and pi > 1:
                            break
            fh.close()
            br.close()
        log(f"DONE {len(self.rows)} -> {path}")
        return self.rows


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--delay", type=float, default=1.5)
    ap.add_argument("--pages", type=int, default=3)
    ap.add_argument("--qfile", default=None)
    ap.add_argument("--mode", default="both", choices=["both", "boards", "search"])
    ap.add_argument("--only-boards", default=None,
                    help="逗号分隔的板块 slug")
    a = ap.parse_args()
    ob = set(a.only_boards.split(",")) if a.only_boards else None
    c = Collector(delay=a.delay, pages=a.pages)
    c.run(a.out, mode=a.mode, qfile=a.qfile, only_boards=ob)
