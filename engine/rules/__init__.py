"""Rules engine module for CueCheck."""

from engine.rules.caption_rules import (
    check_cpl,
    check_cps,
    check_duration,
    check_empty,
    check_gap_and_overlap,
    check_lines,
    check_order,
    check_tag_format,
    run_caption_rules,
)
from engine.rules.semantic import (
    check_ad_gap,
    check_ad_onscreen_text,
    check_ad_overlaps_dialogue,
    check_ad_reading_rate,
    check_sdh_missing_sfx,
    check_sdh_missing_speaker_id,
    run_semantic_rules,
)

__all__ = [
    "run_caption_rules",
    "check_empty",
    "check_order",
    "check_duration",
    "check_cps",
    "check_cpl",
    "check_lines",
    "check_gap_and_overlap",
    "check_tag_format",
    "run_semantic_rules",
    "check_sdh_missing_sfx",
    "check_sdh_missing_speaker_id",
    "check_ad_overlaps_dialogue",
    "check_ad_gap",
    "check_ad_onscreen_text",
    "check_ad_reading_rate",
]
