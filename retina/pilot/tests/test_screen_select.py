import pandas as pd

from retina_pilot.score import screen
from retina_pilot.transform import select


def _pool(n=40):
    rows = []
    for i in range(n):
        rows.append({
            "unit_id": f"cbsa:{10000 + i}" if i % 2 == 0 else f"county:{20000 + i}",
            "unit_type": "cbsa" if i % 2 == 0 else "county",
            "unit_name": f"Unit {i}",
            "state": ["CA", "TX", "FL", "NY", "MT", "AL", "OH", "GA"][i % 8],
            "mac": ["JE", "JH", "JN", "JK", "JF", "JJ", "J15", "JJ"][i % 8],
            "pop65": 10000 + 500 * i,
            "medicare_benes": 8000 + 400 * i,
            "ma_pct": 30 + i,
            "svi": (i % 10) / 10,
            "retina_providers": i % 7,
            "rucc": 8 if i % 2 else 2,
        })
    return pd.DataFrame(rows)


def test_screen_score_range_and_direction():
    scored = screen.score_screen(_pool())
    assert scored["screen_score"].between(0, 100).all()
    # lowest-supply, highest-need unit should outrank highest-supply, lowest-need
    top = scored.sort_values("screen_score", ascending=False).iloc[0]
    assert top["retina_per_10k_65"] <= scored["retina_per_10k_65"].median()


def test_select_pilot_constraints():
    scored = screen.score_screen(_pool())
    picked = select.select_pilot(scored, n=10)
    assert len(picked) == 10
    types = [p["unit_type"] for p in picked]
    assert types.count("cbsa") >= 4
    assert types.count("county") >= 3
    assert len({p["mac"] for p in picked}) >= 4
    assert len({p["unit_id"] for p in picked}) == 10
