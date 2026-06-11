"""Load the seven extracted PUF text files into raw_*.parquet with validation."""
from pathlib import Path

import duckdb

from .. import layouts


def load_all(raw_dir: Path, out_dir: Path, bounds: dict | None = None) -> dict[str, int]:
    bounds = bounds if bounds is not None else layouts.ROW_BOUNDS
    out_dir.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect()
    counts: dict[str, int] = {}
    for layout in layouts.LAYOUTS.values():
        path = layouts.find_raw_file(layout, raw_dir)
        layouts.validate_header(layout, path)
        cols = ", ".join(f"'{c}': 'VARCHAR'" for c in layout.columns)
        out = out_dir / f"raw_{layout.key}.parquet"
        con.execute(
            f"""
            COPY (
                SELECT * FROM read_csv(
                    '{path.as_posix()}', delim='|', header=true,
                    columns={{{cols}}}, encoding='{layout.encoding}',
                    all_varchar=true
                )
            ) TO '{out.as_posix()}' (FORMAT PARQUET)
            """
        )
        n = con.execute(
            f"SELECT count(*) FROM read_parquet('{out.as_posix()}')"
        ).fetchone()[0]
        lo, hi = bounds[layout.key]
        if not lo <= n <= hi:
            raise ValueError(
                f"{layout.key}: {n} rows outside expected bounds [{lo}, {hi}]"
            )
        counts[layout.key] = n
        print(f"ingest: {layout.key:<10} {n:>9,} rows -> {out.name}")
    return counts
