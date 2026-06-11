from pathlib import Path

import pytest

from mpdp_formulary import layouts


def _touch(d: Path, name: str, text: str = "X|Y\n1|2\n", encoding: str = "utf-8"):
    (d / name).write_text(text, encoding=encoding)


def test_find_raw_file_picks_full_file_not_sample(tmp_path):
    _touch(tmp_path, "basic drugs formulary file  20260531.txt")
    _touch(tmp_path, "basic drugs formulary file sample 20260531.txt")
    layout = layouts.LAYOUTS["basic"]
    assert layouts.find_raw_file(layout, tmp_path).name == "basic drugs formulary file  20260531.txt"


def test_find_raw_file_no_prefix_collision(tmp_path):
    _touch(tmp_path, "beneficiary cost file  20260531.txt")
    _touch(tmp_path, "insulin beneficiary cost file  20260531.txt")
    assert "insulin" not in layouts.find_raw_file(layouts.LAYOUTS["bene_cost"], tmp_path).name
    assert "insulin" in layouts.find_raw_file(layouts.LAYOUTS["insulin"], tmp_path).name


def test_find_raw_file_missing_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        layouts.find_raw_file(layouts.LAYOUTS["geo"], tmp_path)


def test_validate_header_accepts_case_insensitive(tmp_path):
    layout = layouts.LAYOUTS["indication"]
    _touch(tmp_path, "indication based coverage formulary file  20260531.txt",
           "contract_id|plan_id|rxcui|disease\nH1|001|123|ASTHMA\n")
    path = layouts.find_raw_file(layout, tmp_path)
    layouts.validate_header(layout, path)  # must not raise


def test_validate_header_rejects_wrong_columns(tmp_path):
    layout = layouts.LAYOUTS["indication"]
    _touch(tmp_path, "indication based coverage formulary file  20260531.txt",
           "CONTRACT_ID|PLAN_ID|BAD\nH1|001|x\n")
    path = layouts.find_raw_file(layout, tmp_path)
    with pytest.raises(ValueError, match="header mismatch"):
        layouts.validate_header(layout, path)


def test_all_layouts_have_bounds():
    assert set(layouts.ROW_BOUNDS) == set(layouts.LAYOUTS)
