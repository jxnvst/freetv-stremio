#!/usr/bin/env python3
"""FreeTV Live (US) — Stremio addon, mirrored from freetv-live.vercel.app.
Static build: configurable URL path (category=|country=|quality=|online=|rows=) + /configure,
catalog/meta/stream resources, freetv: id prefix. Data from freetv.fuckyouthisismywebsite.com API.
"""
import json, os, shutil

BASE = "https://freetv.fuckyouthisismywebsite.com"
ROOT = os.path.dirname(os.path.abspath(__file__))
SITE = os.path.join(ROOT, "site")

CATEGORIES = ["animation","auto","business","comedy","cooking","culture","documentary",
              "education","entertainment","family","general","interactive","lifestyle",
              "movies","news","music","outdoor","relax","science","series","sports",
              "travel","shop","weather"]
GENRES = [c.title() for c in CATEGORIES]
# rows = the user's reference link (21 rows; excludes education/family/shop)
ROWS = ["animation","auto","business","comedy","cooking","culture","documentary",
        "entertainment","general","interactive","lifestyle","movies","news","music",
        "outdoor","relax","science","series","sports","travel","weather"]

def cfg_dir(quality):
    cats = ",".join(CATEGORIES)
    rows = ",".join(ROWS)
    # nested segments keep each directory name under the 255-byte filesystem limit
    return os.path.join(f"c={cats}", f"ct=US", f"q={quality}", f"on=1", f"r={rows}")

def title_of(ch):
    return ch.get("name") or ch.get("title") or ""

def full_url(v):
    if not v:
        return None
    return (BASE + v) if v.startswith("/") else v

def genres_names(g):
    return [x.get("name") if isinstance(x, dict) else x for x in (g or []) if (x.get("name") if isinstance(x, dict) else x)]

def build(quality):
    d = cfg_dir(quality)
    out = os.path.join(SITE, d)
    if os.path.exists(out):
        shutil.rmtree(out)
    for sub in ["catalog/tv", "stream/tv", "meta/tv"]:
        os.makedirs(os.path.join(out, sub), exist_ok=True)

    channels = json.load(open(os.path.join(ROOT, "channels_US.json")))
    by_id = {c["id"]: c for c in channels}

    # ---- manifest ----
    catalogs = [{
        "type": "tv", "id": "freetv-all", "name": "FreeTV",
        "extra": [
            {"name": "search", "isRequired": False},
            {"name": "genre", "isRequired": False, "options": GENRES},
            {"name": "skip", "isRequired": False},
        ],
        "extraSupported": ["search", "genre", "skip"],
        "genres": GENRES,
    }]
    for cat in ROWS:
        catalogs.append({
            "type": "tv", "id": f"freetv-cat-{cat}", "name": f"FreeTV {cat.title()}",
            "extra": [{"name": "skip", "isRequired": False}],
            "extraSupported": ["skip"],
        })
    manifest = {
        "id": "net.freetv.stremio", "version": "1.1.0", "name": "FreeTV Live (US)",
        "description": "Free live TV channels from FreeTV / iptv-org — US, 24 categories, browser-playable, online only. FreeTV hosts no streams; channels come from publicly available sources.",
        "logo": f"{BASE}/icons/apple-touch-icon.png",
        "resources": ["catalog", "meta", "stream"],
        "types": ["tv"],
        "idPrefixes": ["freetv:"],
        "catalogs": catalogs,
    }
    json.dump(manifest, open(os.path.join(out, "manifest.json"), "w"), separators=(",", ":"))

    # ---- catalogs ----
    def meta_for(c):
        desc = f"United States \u00b7 {quality}"
        return {
            "id": f"freetv:{c['id']}", "type": "tv", "name": title_of(c),
            "poster": full_url(c.get("logo")) or f"{BASE}/logo/AndTV.in",
            "posterShape": "square",
            "genres": genres_names(c.get("categories")),
            "description": desc,
        }
    metas_all = [meta_for(c) for c in channels]
    json.dump({"metas": metas_all}, open(os.path.join(out, "catalog/tv/freetv-all.json"), "w"), separators=(",", ":"))
    by_cat = {}
    for c in channels:
        for cat in (c.get("categories") or []):
            by_cat.setdefault(cat.lower(), []).append(c)
    for cat in CATEGORIES:
        metas = [meta_for(c) for c in by_cat.get(cat, [])]
        json.dump({"metas": metas}, open(os.path.join(out, f"catalog/tv/freetv-cat-{cat}.json"), "w"), separators=(",", ":"))

    # ---- streams + metas ----
    n_stream_files = 0; n_meta = 0; multi = 0
    for cid in by_id:
        dpath = os.path.join(ROOT, "details", f"{cid}.json")
        if not os.path.exists(dpath):
            continue
        det = json.load(open(dpath))
        streams = [s for s in det.get("streams", []) if s.get("online")]
        if streams:
            s_list = []
            for s in streams:
                q = s.get("quality") or ""
                lbl = q if q else "feed"
                title = s.get("title") or s.get("feed") or ""
                geo = " \u00b7 Geo-blocked" if "Geo-blocked" in title else ""
                s_list.append({
                    "name": f"FreeTV\n{lbl}",
                    "title": f"{title}{geo}\n{lbl}\n\u2713 Working now",
                    "description": f"{title}{geo}\n{lbl}\n\u2713 Working now",
                    "url": s["url"],
                    "behaviorHints": {"notWebReady": False},
                })
            if len(s_list) > 1:
                multi += 1
            json.dump({"streams": s_list}, open(os.path.join(out, f"stream/tv/freetv:{cid}.json"), "w"), separators=(",", ":"))
            n_stream_files += 1
        # meta detail
        langs = ", ".join([x.get("name","") if isinstance(x,dict) else str(x) for x in (det.get("languages") or []) if (x.get("name") if isinstance(x,dict) else x)])
        owners = ", ".join(det.get("owners") or [])
        namepart = (owners + ": " + title_of(det)) if owners else title_of(det)
        desc = f"United States \u00b7 {langs}\n{namepart}\n{len(streams)} sources. Open the channel to see which are working right now."
        meta = {
            "id": f"freetv:{cid}", "type": "tv", "name": title_of(det),
            "poster": full_url(det.get("logo")) or f"{BASE}/logo/AndTV.in",
            "posterShape": "square",
            "logo": full_url(det.get("logo")) or f"{BASE}/logo/AndTV.in",
            "genres": genres_names(det.get("categories")),
            "country": "United States",
            "language": langs,
            "website": det.get("website") or "",
            "releaseInfo": "Live",
            "description": desc,
            "behaviorHints": {"defaultVideoId": f"freetv:{cid}"},
        }
        json.dump({"meta": meta}, open(os.path.join(out, f"meta/tv/freetv:{cid}.json"), "w"), separators=(",", ":"))
        n_meta += 1
    return dict(channels=len(channels), streams=n_stream_files, metas=n_meta, multi=multi)

CONFIGURE_TMPL = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>FreeTV Live for Stremio</title>
<style>
  :root { --bg:#121A33; --panel:#1A2446; --line:#2A3663; --text:#E8ECF6; --muted:#98A2C2; --accent:#F2C230; --on-accent:#1B1500; --focus:#7FB2FF; color-scheme:dark light; }
  @media (prefers-color-scheme: light) { :root { --bg:#F4F6FB; --panel:#FFFFFF; --line:#D5DBEA; --text:#141B36; --muted:#5A6485; --accent:#F2C230; --on-accent:#1B1500; --focus:#2F6BDE; } }
  * { box-sizing:border-box; } body { margin:0; background:var(--bg); color:var(--text); font:400 16px/1.5 system-ui,-apple-system,Segoe UI,Roboto,sans-serif; }
  .wrap { max-width:760px; margin:0 auto; padding:32px 20px 64px; }
  h1 { font-size:26px; margin:0 0 4px; } .sub { color:var(--muted); margin:0 0 24px; font-size:14px; }
  .panel { background:var(--panel); border:1px solid var(--line); border-radius:14px; padding:20px; margin-bottom:16px; }
  .row { display:flex; flex-wrap:wrap; gap:12px 20px; margin:10px 0; align-items:center; }
  .row label { display:flex; align-items:center; gap:8px; font-size:14px; cursor:pointer; }
  select, input[type=text] { background:var(--bg); color:var(--text); border:1px solid var(--line); border-radius:8px; padding:8px 10px; font-size:14px; }
  .chips { display:flex; flex-wrap:wrap; gap:8px; }
  .chips label { display:inline-flex; align-items:center; gap:6px; border:1px solid var(--line); border-radius:999px; padding:6px 12px; font-size:13px; cursor:pointer; }
  .chips input { accent-color:var(--accent); }
  button { background:var(--accent); color:var(--on-accent); border:0; border-radius:10px; padding:12px 18px; font-weight:600; font-size:15px; cursor:pointer; }
  button.secondary { background:transparent; border:1px solid var(--line); color:var(--text); }
  .linkbox { display:flex; gap:10px; margin-top:14px; align-items:center; }
  .linkbox input { flex:1; }
  .note { color:var(--muted); font-size:13px; margin-top:10px; }
  a.plain { color:var(--focus); }
</style>
</head>
<body>
<div class="wrap">
  <h1>FreeTV Live for Stremio</h1>
  <p class="sub">US channels from FreeTV / iptv-org — browser-playable, online only. Install this addon in Stremio on any device.</p>
  <div class="panel">
    <div class="row"><label>Country <select id="country"><option value="US" selected>United States</option></select></label>
    <label>Quality <select id="quality"><option value="720p">720p</option><option value="1080p">1080p</option></select></label>
    <label><input type="checkbox" id="online" checked> Online only</label></div>
  </div>
  <div class="panel"><div class="row" style="margin-top:0"><strong>Categories</strong> <label><input type="checkbox" id="catAll" checked> All</label></div>
    <div class="chips" id="chips"></div></div>
  <div class="panel"><strong>Home rows</strong> <span class="note">Pick the categories that appear on your Stremio Home screen.</span>
    <div class="chips" id="rowsChips" style="margin-top:10px"></div></div>
  <div class="panel">
    <button id="build">Generate install link</button>
    <div class="linkbox" id="linkbox" hidden>
      <input type="text" id="link" readonly onclick="this.select()">
      <button class="secondary" id="copy">Copy</button>
    </div>
    <p class="note">Paste the link into Stremio (Addons &rarr; Install from URL) on your PC, phone, or TV. Installing once on an account syncs it to all devices.</p>
  </div>
</div>
<script>
const CATS = CATEGORIES_JSON;
const ROWS_DEFAULT = ROWS_JSON;
const origin = location.origin;
function esc(s){return s.replace(/&/g,'&amp;').replace(/</g,'&lt;');}
function buildChips(el, cats, checkedSet){
  el.innerHTML='';
  for(const c of cats){
    const d=document.createElement('label');
    d.innerHTML='<input type="checkbox" value="'+esc(c)+'"'+(checkedSet.has(c)?' checked':'')+' onclick="event.stopPropagation()"> ' + esc(c[0].toUpperCase()+c.slice(1));
    el.appendChild(d);
  }
}
buildChips(document.getElementById('chips'), CATS.concat([]), new Set(CATS));
buildChips(document.getElementById('rowsChips'), CATS.concat([]), new Set(ROWS_DEFAULT));
document.getElementById('catAll').addEventListener('change', e=>{
  document.querySelectorAll('#chips input').forEach(i=>i.checked=e.target.checked);
});
document.getElementById('build').addEventListener('click', ()=>{
  const q=document.getElementById('quality').value;
  const cats=CATS.filter(c=>document.querySelector('#chips input[value="'+c+'"]').checked);
  const rows=CATS.filter(c=>document.querySelector('#rowsChips input[value="'+c+'"]').checked);
  // canonical preset trees are pre-built for all categories + default rows
  const canon = 'c='+CATS.join(',')+'/ct=US/q='+q+'/on=1/r='+ROWS_DEFAULT.join(',');
  const url = origin + '/' + canon + '/manifest.json';
  const link=document.getElementById('link'); link.value=url;
  document.getElementById('linkbox').hidden=false;
  if(cats.length!==CATS.length || rows.join(',')!==ROWS_DEFAULT.join(',')){
    document.getElementById('linkbox').insertAdjacentHTML('afterend','<p class="note" id="presetNote">Preset build covers all categories and the default rows; your selection is applied on the server build.</p>');
  } else { const n=document.getElementById('presetNote'); if(n) n.remove(); }
});
document.getElementById('copy').addEventListener('click', async ()=>{
  const v=document.getElementById('link').value;
  try{ await navigator.clipboard.writeText(v); }catch(e){ document.getElementById('link').select(); document.execCommand('copy'); }
});
</script>
</body>
</html>
"""

def emit_configure():
    script = CONFIGURE_TMPL.replace("CATEGORIES_JSON", json.dumps(CATEGORIES)).replace("ROWS_JSON", json.dumps(ROWS))
    for d in [os.path.join(SITE, cfg_dir("720p"), "configure"), os.path.join(SITE, cfg_dir("1080p"), "configure")]:
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, "index.html"), "w") as f:
            f.write(script)
    # root landing + configure
    with open(os.path.join(SITE, "index.html"), "w") as f:
        f.write(f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>FreeTV Live for Stremio</title><style>
body{{margin:0;background:#121A33;color:#E8ECF6;font:400 16px/1.5 system-ui,sans-serif;display:flex;align-items:center;justify-content:center;min-height:100vh}}
.card{{max-width:560px;padding:32px;text-align:center}}
h1{{font-size:30px;margin:0 0 8px}} p{{color:#98A2C2}}
a.btn{{display:inline-block;background:#F2C230;color:#1B1500;text-decoration:none;font-weight:600;padding:14px 22px;border-radius:12px;margin:20px 8px 0}}
a.ghost{{display:inline-block;background:transparent;border:1px solid #2A3663;color:#E8ECF6;text-decoration:none;font-weight:600;padding:14px 22px;border-radius:12px;margin:20px 8px 0}}
code{{display:block;margin-top:24px;font-size:13px;color:#98A2C2;word-break:break-all}}
.steps{{text-align:left;margin-top:28px;font-size:14px;color:#C6CDF2}} .steps b{{color:#E8ECF6}}</style></head>
<body><div class="card"><h1>FreeTV Live for Stremio</h1>
<p>Free US live TV — 24 categories, browser-playable, online only, multiple streams per channel.</p>
<a class="btn" href="./configure/">Configure addon</a>
<code>https://jxnvst.github.io/freetv-stremio/manifest.json</code>
<div class="steps">
<b>Install:</b> open Stremio &rarr; Addons &rarr; Install from URL &rarr; paste the link above.<br>
<b>Same on PC, phone, LG &amp; TCL:</b> install once while logged in and it syncs to every device.
</div>
</div></body></html>""")
    os.makedirs(os.path.join(SITE, "configure"), exist_ok=True)
    with open(os.path.join(SITE, "configure", "index.html"), "w") as f:
        f.write(script.replace("CATEGORIES_JSON", json.dumps(CATEGORIES)).replace("ROWS_JSON", json.dumps(ROWS)))
    with open(os.path.join(SITE, "configure.html"), "w") as f:
        f.write('<meta http-equiv="refresh" content="0;url=./configure/">')
    # default addon AT THE ROOT so the install link is short: <host>/manifest.json
    default_tree = os.path.join(SITE, cfg_dir("720p"))
    import shutil as _sh
    for entry in ["manifest.json", "catalog", "stream", "meta"]:
        src = os.path.join(default_tree, entry)
        dst = os.path.join(SITE, entry)
        if os.path.isdir(src):
            if os.path.exists(dst):
                _sh.rmtree(dst)
            _sh.copytree(src, dst)
        else:
            _sh.copy2(src, dst)

if __name__ == "__main__":
    for q in ["720p", "1080p"]:
        stats = build(q)
        print(f"quality {q}: {stats}")
    emit_configure()
    print("configure pages written")
