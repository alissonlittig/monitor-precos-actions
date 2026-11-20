import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import tracker


def test_alerts_and_chart():
    cfg = {"products": [{"id": "a", "name": "A", "source": "x", "target": 10}, {"id": "b", "name": "B", "source": "x", "target": 5}]}
    hist = {"a": [["t1", 12], ["t2", 9]], "b": [["t1", 6]]}
    assert [p["id"] for p, _ in tracker.alerts(cfg, hist)] == ["a"]
    assert "<polyline" in tracker.svg_chart(hist["a"], 10)
    assert tracker.money(1234.5, "BRL") == "R$ 1.234,50"
