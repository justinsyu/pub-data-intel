"""National screen score: need-versus-supply vulnerability (0-100)."""
import pandas as pd


def score_screen(units: pd.DataFrame) -> pd.DataFrame:
    df = units.copy()
    df["retina_per_10k_65"] = (10000 * df["retina_providers"] / df["pop65"]).round(3)
    need_up = ["pop65", "svi", "ma_pct"]      # higher value = higher need
    supply_down = ["retina_per_10k_65"]        # higher value = lower need
    parts = [df[c].rank(pct=True) for c in need_up]
    parts += [1 - df[c].rank(pct=True) for c in supply_down]
    df["screen_score"] = (100 * sum(parts) / len(parts)).round(1)
    return df
