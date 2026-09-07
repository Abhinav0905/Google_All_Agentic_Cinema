"""Tests for profile loading, validation, and source documentation."""

from engine.profiles import list_profiles, load_profile


def test_load_profiles():
    adult = load_profile("adult")
    assert adult.id == "adult"
    assert adult.max_cps.value == 20
    assert adult.max_cps.source != ""
    assert adult.max_chars_per_line.value == 42
    assert adult.max_lines.value == 2
    assert adult.min_duration_ms.value == 833
    assert adult.max_duration_ms.value == 7000
    assert adult.min_gap_ms.value == 83
    assert adult.sync_tolerance_ms.value == 500
    assert adult.ad_overlap_tolerance_ms.value == 250
    assert adult.ad_max_wpm.value == 180

    kids = load_profile("kids")
    assert kids.id == "kids"
    assert kids.max_cps.value == 17
    assert kids.max_cps.source != ""
    assert kids.ad_max_wpm.value == 160

    # Ensure all pass thresholds have sources
    for dim in ["accuracy", "synchronicity", "completeness", "readability", "sdh", "ad"]:
        assert dim in adult.pass_thresholds
        assert adult.pass_thresholds[dim].source != ""
        assert adult.pass_thresholds[dim].value > 0


def test_list_profiles():
    profiles = list_profiles()
    ids = [p["id"] for p in profiles]
    assert "adult" in ids
    assert "kids" in ids
