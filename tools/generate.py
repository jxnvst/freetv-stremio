#!/usr/bin/env python3
"""Generate a fully static Stremio addon from FreeTV's public API.

Output: a GitHub Pages-ready tree:
  manifest.json
  catalog/tv/<id>.json     (curated US category catalogs)
  stream/tv/<channel>.json (all online streams per channel)
"""
import json, os, sys, time, urllib.request, urllib.parse, threading
from concurrent.futures import ThreadPoolExecutor, as_completed

BASE = "https://freetv.fuckyouthisismywebsite.com"
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "site")
CACHE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cache")
UA = {"User-Agent": "Mozilla/5.0 (stremio-freetv-addon/1.0)"}
os.makedirs(CACHE, exist_ok=True)

CATS = ["animation","auto","business","comedy","cooking","culture","documentary",
        "entertainment","education","family","general","interactive","lifestyle",
        "movies","news","music","outdoor","relax","science","series","sports",
        "travel","shop","weather"]

def get(path, timeout=40, tries=3):
    url = BASE + path
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.loads(r.read().decode())
        except Exception:
            time.sleep(1.5 * (i + 1))
    return None

def fetch_channels(country="US"):
    cache_f = os.path.join(CACHE, f"channels_{country}.json")
    if os.path.exists(cache_f):
        return json.load(open(cache_f))
    channels, page, limit = [], 1, 100
    while True:
        j = get(f"/api/channels?country={country}&page={page}&limit={limit}")
        if not j or not j.get("items"):
            break
        channels += j["items"]
        total = j.get("total", 0)
        if len(channels) >= total or len(j["items"]) < limit:
            break
        page += 1
    json.dump(channels, open(cache_f, "w"))
    return channels

def fetch_detail(ch_id):
    cache_f = os.path.join(CACHE, f"detail_{urllib.parse.quote(ch_id, safe='')}.json")
    if os.path.exists(cache_f):
        return ch_id, json.load(open(cache_f))
    j = get(f"/api/channels/{urllib.parse.quote(ch_id, safe='')}")
    if j:
        json.dump(j, open(cache_f, "w"))
    return ch_id, j

def main():
    print("Fetching US channel list...", flush=True)
    channels = fetch_channels("US")
    print(f"  {len(channels)} US channels", flush=True)

    online = [c for c in channels if c.get("online")]
    print(f"Fetching stream details for {len(online)} online channels (threaded)...", flush=True)
    details = {}
    with ThreadPoolExecutor(max_workers=24) as ex:
        futs = {ex.submit(fetch_detail, c["id"]): c["id"] for c in online}
        for k, fut in enumerate(as_completed(futs), 1):
            cid, j = fut.result()
            if j and j.get("streams"):
                details[cid] = j
            if k % 200 == 0:
                print(f"    {k}/{len(online)}", flush=True)

    os.makedirs(os.path.join(OUT, "catalog", "tv"), exist_ok=True)
    os.makedirs(os.path.join(OUT, "stream", "tv"), exist_ok=True)

    manifest = {
        "id": "net.freetv.stremio",
        "version": "1.0.0",
        "name": "FreeTV",
        "description": "Free live TV channels (US) via FreeTV's public API.",
        "logo": f"{BASE}/logo/AndTV.in",
        "resources": ["catalog", "stream"],
        "types": ["tv"],
        "catalogs": [{"type": "tv", "id": "all", "name": "FreeTV · All US", "extraSupported": ["search","genre"]}]
                  + [{"type": "tv", "id": c, "name": c.capitalize()} for c in CATS],
        "idPrefixes": ["free-"]
    }
    with open(os.path.join(OUT, "manifest.json"), "w") as f:
        json.dump(manifest, f, separators=(",", ":"))
    print("manifest written", flush=True)

    def meta_for(c):
        logo = BASE + (c.get("logo") or "/logo/AndTV.in")
        return {
            "id": c["id"],
            "type": "tv",
            "name": c.get("name") or c["id"],
            "poster": logo,
            "logo": logo,
            "genres": [x.replace("_", " ").capitalize() for x in (c.get("categories") or [])][:4],
        }

    by_cat = {}
    for c in channels:
        for cat in (c.get("categories") or []):
            if cat in CATS:
                by_cat.setdefault(cat, []).append(meta_for(c))

    for cat, metas in by_cat.items():
        with open(os.path.join(OUT, "catalog", "tv", f"{cat}.json"), "w") as f:
            json.dump({"metas": metas}, f, separators=(",", ":"))

    with open(os.path.join(OUT, "catalog", "tv", "all.json"), "w") as f:
        json.dump({"metas": [meta_for(c) for c in channels]}, f, separators=(",", ":"))

    # This addon answers only pre-generated catalogs; a search returns empty.
    with open(os.path.join(OUT, "catalog", "tv", "search.json"), "w") as f:
        json.dump({"metas": []}, f, separators=(",", ":"))

    written = 0
    for cid, det in details.items():
        streams = []
        for s in det.get("streams") or []:
            if not s.get("online"):
                continue
            q = s.get("quality") or ""
            rank = (
                0 if s.get("browserPlayable") else 1,
                0 if "1080" in q else (1 if "720" in q else 2),
            )
            streams.append({
                "url": s["url"],
                "title": " · ".join(x for x in [
                    q, s.get("feed"), s.get("title")
                ] if x),
                "behaviorHints": {"bingeGroup": "free-" + cid, "order": list(rank)},
            })
        if streams:
            # multiple stream options: browserPlayable first, then quality desc
            streams.sort(key=lambda s: s["behaviorHints"]["order"])
            for st in streams:
                st["behaviorHints"].pop("order", None)
            with open(os.path.join(OUT, "stream", "tv", f"{cid}.json"), "w") as f:
                json.dump({"streams": streams}, f, separators=(",", ":"))
            written += 1

    print(f"done: {len(details)} channels with streams, {written} stream files, "
          f"{len(channels)} catalog entries", flush=True)

if __name__ == "__main__":
    main()
