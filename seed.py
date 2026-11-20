"""Opcional: preenche 30 dias de historico real (CoinGecko) para o grafico nao nascer vazio."""
import json, os, yaml, tracker
from datetime import datetime, timezone

cfg = yaml.safe_load(open("products.yaml", encoding="utf-8"))
hist = {}
for p in cfg["products"]:
    if p["source"] != "coingecko":
        continue
    d = tracker.get_json(f"https://api.coingecko.com/api/v3/coins/{p['id']}/market_chart?vs_currency=brl&days=30&interval=daily")
    hist[p["id"]] = [[datetime.fromtimestamp(t / 1000, timezone.utc).replace(microsecond=0).isoformat(), v] for t, v in d["prices"][:-1]]
os.makedirs("data", exist_ok=True)
json.dump(hist, open(tracker.HIST, "w", encoding="utf-8"), indent=1)
print({k: len(v) for k, v in hist.items()})
