"""Monitor de precos: coleta -> historico JSON/CSV -> pagina com graficos + badge + RSS."""
import csv, json, os, sys, urllib.request, html
from datetime import datetime, timezone
from email.utils import format_datetime
import yaml

ROOT = os.path.dirname(os.path.abspath(__file__))
HIST = os.path.join(ROOT, "data", "history.json")
UA = {"User-Agent": "price-monitor-portfolio/1.0"}
SITE = "https://alissonlittig.github.io/monitor-precos-actions/"


def get_json(url, headers=None):
    req = urllib.request.Request(url, headers={**UA, **(headers or {})})
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.load(r)


def fetch_coingecko(products, cur):
    ids = ",".join(p["id"] for p in products)
    d = get_json(f"https://api.coingecko.com/api/v3/simple/price?ids={ids}&vs_currencies={cur.lower()}")
    return {p["id"]: d[p["id"]][cur.lower()] for p in products if p["id"] in d}


def fetch_ml(products, cur):
    tok = os.environ.get("ML_TOKEN")
    if not tok:  # a API do ML exige OAuth; sem token a fonte e pulada
        print("aviso: ML_TOKEN ausente, itens do Mercado Livre ignorados", file=sys.stderr)
        return {}
    return {p["id"]: get_json(f"https://api.mercadolibre.com/items/{p['id']}",
                              {"Authorization": f"Bearer {tok}"})["price"] for p in products}


SOURCES = {"coingecko": fetch_coingecko, "mercadolivre": fetch_ml}


def collect(cfg, now):
    hist = json.load(open(HIST, encoding="utf-8")) if os.path.exists(HIST) else {}
    for src, fn in SOURCES.items():
        items = [p for p in cfg["products"] if p["source"] == src]
        if not items:
            continue
        try:
            prices = fn(items, cfg.get("currency", "BRL"))
        except Exception as e:  # uma fonte fora do ar nao derruba as outras
            print(f"erro na fonte {src}: {e}", file=sys.stderr)
            continue
        for pid, price in prices.items():
            hist.setdefault(pid, []).append([now, price])
    return hist


def alerts(cfg, hist):
    return [(p, hist[p["id"]][-1][1]) for p in cfg["products"]
            if hist.get(p["id"]) and hist[p["id"]][-1][1] < p["target"]]


def svg_chart(points, target, w=520, h=150):
    ys = [v for _, v in points] + [target]
    lo, hi = min(ys), max(ys)
    span = (hi - lo) or 1
    n = max(len(points) - 1, 1)
    X = lambda i: 8 + i * (w - 16) / n
    Y = lambda v: h - 12 - (v - lo) / span * (h - 28)
    pts = " ".join(f"{X(i):.1f},{Y(v):.1f}" for i, (_, v) in enumerate(points))
    area = f"{X(0):.1f},{h-12} {pts} {X(len(points)-1):.1f},{h-12}"
    return (f'<svg viewBox="0 0 {w} {h}" role="img" aria-label="historico de preco">'
            f'<defs><linearGradient id="g" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#7c5cff" stop-opacity=".35"/>'
            f'<stop offset="1" stop-color="#7c5cff" stop-opacity="0"/></linearGradient></defs>'
            f'<line x1="8" x2="{w-8}" y1="{Y(target):.1f}" y2="{Y(target):.1f}" stroke="#ff6b81" stroke-dasharray="4 4"/>'
            f'<polygon points="{area}" fill="url(#g)"/><polyline points="{pts}" fill="none" stroke="#a594ff" stroke-width="2.2" stroke-linejoin="round"/>'
            f'<circle cx="{X(len(points)-1):.1f}" cy="{Y(points[-1][1]):.1f}" r="4" fill="#fff"/></svg>')


def money(v, cur):
    s = f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return ("R$ " if cur == "BRL" else cur + " ") + s


CSS = """:root{color-scheme:dark}*{box-sizing:border-box}body{margin:0;font-family:Inter,system-ui,Segoe UI,sans-serif;background:radial-gradient(1200px 600px at 10% -10%,#2a1f5c,#0d0f1a 60%);color:#e8e9f3;min-height:100vh}
main{max-width:1100px;margin:0 auto;padding:48px 20px}h1{font-size:clamp(1.8rem,4vw,2.8rem);margin:0 0 6px;letter-spacing:-.02em}p.sub{color:#9aa0c0;margin:0 0 28px}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(310px,1fr));gap:18px}.card{background:#141729;border:1px solid #262a47;border-radius:16px;padding:18px}
.card.hit{border-color:#ff6b81}header{display:flex;justify-content:space-between;align-items:center;gap:8px}h2{font-size:1.05rem;margin:0}
.tag{font-size:.68rem;background:#ff6b8133;color:#ffa3b2;padding:3px 8px;border-radius:99px}.price{font-size:1.7rem;font-weight:700;margin:10px 0 4px}
small{font-size:.8rem;margin-left:10px;font-weight:600}.up{color:#4ade80}.dn{color:#ffa3b2}svg{width:100%;height:auto}footer{color:#8a90b3;font-size:.78rem;margin-top:6px}
nav{margin-top:28px;color:#9aa0c0;font-size:.85rem}a{color:#a594ff}"""


def build(cfg, hist, now):
    cur = cfg.get("currency", "BRL")
    al = alerts(cfg, hist)
    hit = {p["id"] for p, _ in al}
    cards = ""
    for p in cfg["products"]:
        h = hist.get(p["id"])
        if not h:
            continue
        last, first = h[-1][1], h[0][1]
        chg = (last - first) / first * 100 if first else 0
        flag = '<span class="tag">abaixo do alvo · below target</span>' if p["id"] in hit else ""
        cards += (f'<article class="card{" hit" if flag else ""}"><header><h2>{html.escape(p["name"])}</h2>{flag}</header>'
                  f'<div class="price">{money(last, cur)}<small class="{"dn" if chg < 0 else "up"}">{chg:+.1f}%</small></div>'
                  f'{svg_chart(h, p["target"])}<footer>alvo/target {money(p["target"], cur)} · min {money(min(v for _, v in h), cur)} · {len(h)} pts</footer></article>')
    page = f"""<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Monitor de Preços · Price Monitor</title><link rel="alternate" type="application/rss+xml" href="feed.xml"><style>{CSS}</style></head><body><main>
<h1>Monitor de Preços</h1><p class="sub">Atualizado via GitHub Actions · Auto-updated by GitHub Actions · {now[:16].replace("T", " ")} UTC</p>
<div class="grid">{cards}</div><nav><a href="feed.xml">RSS</a> · <a href="badge.svg">badge</a> · <a href="https://github.com/alissonlittig/monitor-precos-actions">código / source</a></nav></main></body></html>"""
    d = os.path.join(ROOT, "docs")
    os.makedirs(d, exist_ok=True)
    open(os.path.join(d, "index.html"), "w", encoding="utf-8").write(page)
    col = "#e5484d" if al else "#2f9e63"
    txt = f"{len(al)} alerta" + ("" if len(al) == 1 else "s")
    open(os.path.join(d, "badge.svg"), "w", encoding="utf-8").write(
        f'<svg xmlns="http://www.w3.org/2000/svg" width="130" height="20"><rect width="70" height="20" rx="3" fill="#555"/><rect x="70" width="60" height="20" rx="3" fill="{col}"/>'
        f'<g fill="#fff" font-family="Verdana" font-size="11" text-anchor="middle"><text x="35" y="14">precos</text><text x="100" y="14">{txt}</text></g></svg>')
    items = "".join(
        f"<item><title>{html.escape(p['name'])} abaixo do alvo: {money(v, cur)}</title><link>{SITE}</link>"
        f"<guid isPermaLink='false'>{p['id']}-{now}</guid><pubDate>{format_datetime(datetime.fromisoformat(now))}</pubDate></item>"
        for p, v in al)
    open(os.path.join(d, "feed.xml"), "w", encoding="utf-8").write(
        f'<?xml version="1.0" encoding="UTF-8"?><rss version="2.0"><channel><title>Alertas de preço</title>'
        f'<link>{SITE}</link><description>Produtos abaixo do alvo</description>{items}</channel></rss>')
    with open(os.path.join(ROOT, "data", "history.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["id", "timestamp", "price"])
        for pid, h in hist.items():
            w.writerows([pid, t, v] for t, v in h)


def main():
    cfg = yaml.safe_load(open(os.path.join(ROOT, "products.yaml"), encoding="utf-8"))
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    hist = collect(cfg, now)
    os.makedirs(os.path.dirname(HIST), exist_ok=True)
    json.dump(hist, open(HIST, "w", encoding="utf-8"), indent=1)
    build(cfg, hist, now)
    print("ok", {k: v[-1][1] for k, v in hist.items()})


if __name__ == "__main__":
    main()
