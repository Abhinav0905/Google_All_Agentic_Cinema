"""Deterministic Fixer for timed-text cues and Audio Description.

Generates proposed Fix objects with before/after cue states:
- extend: push end_ms later up to next.start_ms - min_gap_ms (for DUR_MIN or CPS)
- re-wrap: break text into <= max_lines lines of <= max_chars_per_line at clause boundaries
- split: divide cue into two at clause boundary, time proportional to chars, both >= min_duration
- trim: pull end_ms back to fix GAP_MIN / OVERLAP
- global_shift: shift cues from first affected cue onward if consistent median offset detected
- insert_tag_cue: create bracketed cue from SDH_MISSING_SFX
- prepend_speaker_label: prepend speaker identification from SDH_MISSING_SPEAKER_ID
- retime_ad: move AD cue into nearest dialogue silence
- normalize_tag: convert parentheses to brackets or add paired music note
- delete: remove empty cues
"""

import re
from typing import Dict, List, Optional, Tuple

from engine.alignment import AlignmentResult
from engine.models import Cue, Finding, Fix, Profile, Segment


def plan_fix_empty(finding: Finding, cue: Cue) -> Fix:
    """Propose deleting empty cue."""
    return Fix(
        id=f"FIX_{finding.id}",
        finding_ids=[finding.id],
        type="delete",
        before=cue.model_copy(),
        after=None,  # None signifies deletion
        auto=True,
        status="proposed",
    )


def plan_fix_trim(
    finding: Finding, cue: Cue, next_cue: Cue, profile: Profile
) -> Optional[Fix]:
    """Trim cue.end_ms so that cue.end_ms <= next_cue.start_ms - min_gap_ms."""
    min_gap = profile.min_gap_ms.value
    min_dur = profile.min_duration_ms.value
    target_end = next_cue.start_ms - min_gap

    # Must preserve min_duration
    if target_end - cue.start_ms >= min_dur:
        after_cue = cue.model_copy()
        after_cue.end_ms = target_end
        return Fix(
            id=f"FIX_{finding.id}",
            finding_ids=[finding.id],
            type="trim",
            before=cue.model_copy(),
            after=after_cue,
            auto=True,
            status="proposed",
        )
    return None


def plan_fix_extend(
    finding: Finding,
    cue: Cue,
    next_cue: Optional[Cue],
    profile: Profile,
    target_cps: Optional[float] = None,
) -> Optional[Fix]:
    """Extend cue.end_ms into following gap to satisfy DUR_MIN or reduce CPS."""
    min_gap = profile.min_gap_ms.value
    max_dur = profile.max_duration_ms.value

    # Maximum available end_ms before colliding with next cue or max_dur
    avail_end = (next_cue.start_ms - min_gap) if next_cue else (cue.start_ms + max_dur)
    max_allowed_end = min(avail_end, cue.start_ms + max_dur)

    if finding.code == "DUR_MIN":
        needed_end = cue.start_ms + profile.min_duration_ms.value
        if needed_end <= max_allowed_end:
            after_cue = cue.model_copy()
            after_cue.end_ms = needed_end
            return Fix(
                id=f"FIX_{finding.id}",
                finding_ids=[finding.id],
                type="extend",
                before=cue.model_copy(),
                after=after_cue,
                auto=True,
                status="proposed",
            )

    elif finding.code == "CPS":
        # Extend end_ms to bring CPS down to max_cps
        req_cps = target_cps or profile.max_cps.value
        clean_len = len(re.sub(r"<[^>]+>", "", cue.raw_text).strip())
        needed_duration_s = clean_len / req_cps
        needed_end = cue.start_ms + int(round(needed_duration_s * 1000))

        if needed_end <= max_allowed_end:
            after_cue = cue.model_copy()
            after_cue.end_ms = needed_end
            return Fix(
                id=f"FIX_{finding.id}",
                finding_ids=[finding.id],
                type="extend",
                before=cue.model_copy(),
                after=after_cue,
                auto=True,
                status="proposed",
            )

    return None


def wrap_text_lines(text: str, max_lines: int, max_cpl: int) -> Optional[List[str]]:
    """Greedy wrap text at clause boundaries / word boundaries into <= max_lines lines."""
    words = text.replace("\n", " ").split()
    if not words:
        return []

    lines: List[str] = []
    curr_line: List[str] = []

    for w in words:
        candidate = " ".join(curr_line + [w]) if curr_line else w
        if len(candidate) <= max_cpl:
            curr_line.append(w)
        else:
            if curr_line:
                lines.append(" ".join(curr_line))
                curr_line = [w]
            else:
                # Single word exceeds line length limit
                return None

    if curr_line:
        lines.append(" ".join(curr_line))

    if len(lines) <= max_lines:
        return lines
    return None


def plan_fix_rewrap(
    finding: Finding, cue: Cue, profile: Profile
) -> Optional[Fix]:
    """Re-wrap text lines to satisfy max_lines and max_chars_per_line."""
    max_lines = profile.max_lines.value
    max_cpl = profile.max_chars_per_line.value

    wrapped = wrap_text_lines(cue.text, max_lines, max_cpl)
    if wrapped and wrapped != cue.lines:
        after_cue = cue.model_copy()
        after_cue.lines = wrapped
        after_cue.raw_text = "\n".join(wrapped)
        return Fix(
            id=f"FIX_{finding.id}",
            finding_ids=[finding.id],
            type="re-wrap",
            before=cue.model_copy(),
            after=after_cue,
            auto=True,
            status="proposed",
        )
    return None


def plan_fix_split(
    finding: Finding, cue: Cue, profile: Profile
) -> Optional[Tuple[Cue, Cue]]:
    """Split cue into two parts proportionally at sentence or clause boundary."""
    min_dur = profile.min_duration_ms.value
    if cue.duration_ms < (min_dur * 2):
        return None

    text = cue.text.replace("\n", " ")
    # Search for sentence or clause boundary near middle
    midpoint = len(text) // 2
    best_split_idx = -1
    best_dist = len(text)

    delimiters = [". ", "! ", "? ", ", ", "; ", " -- ", " - ", " "]
    for delim in delimiters:
        for m in re.finditer(re.escape(delim), text):
            pos = m.end()
            dist = abs(pos - midpoint)
            if dist < best_dist:
                part1_len = len(text[:pos].strip())
                # Check proportional durations
                total_len = len(text.strip())
                dur1 = int(cue.duration_ms * (part1_len / total_len))
                dur2 = cue.duration_ms - dur1
                if dur1 >= min_dur and dur2 >= min_dur:
                    best_dist = dist
                    best_split_idx = pos

    if best_split_idx != -1:
        text1 = text[:best_split_idx].strip()
        text2 = text[best_split_idx:].strip()

        ratio = len(text1) / max(len(text1) + len(text2), 1)
        split_time = cue.start_ms + int(cue.duration_ms * ratio)

        cue1 = Cue(
            index=cue.index,
            start_ms=cue.start_ms,
            end_ms=split_time,
            lines=[text1],
            raw_text=text1,
            kind=cue.kind,
        )
        cue2 = Cue(
            index=cue.index,  # Will be renumbered on apply
            start_ms=split_time + profile.min_gap_ms.value,
            end_ms=cue.end_ms,
            lines=[text2],
            raw_text=text2,
            kind=cue.kind,
        )
        return cue1, cue2
    return None


def plan_fix_global_shift(
    alignment: AlignmentResult, cues: List[Cue], profile: Profile
) -> Optional[Fix]:
    """Propose shift from first affected cue onward if offset > tolerance and >=80% cluster."""
    if not alignment.matches:
        return None

    sync_tol = profile.sync_tolerance_ms.value
    median = alignment.median_offset_ms

    # Check 1: whole-file clustering
    if median is not None and abs(median) > sync_tol:
        clustered = [m for m in alignment.matches if abs(m.offset_ms - median) <= 300]
        if len(clustered) / len(alignment.matches) >= 0.80:
            first_affected = min(clustered, key=lambda m: m.cue.start_ms).cue
            after_cue = first_affected.model_copy()
            after_cue.start_ms = median  # Store shift amount in metadata
            return Fix(
                id="FIX_GLOBAL_SHIFT",
                finding_ids=[f.id for f in alignment.findings if f.code == "SYNC_OFFSET"],
                type="global_shift",
                before=first_affected.model_copy(),
                after=after_cue,
                auto=True,
                status="proposed",
            )

    # Check 2: consistent shift in out-of-sync cues (regional/suffix shift)
    out_of_sync = [m for m in alignment.matches if abs(m.offset_ms) > sync_tol]
    if len(out_of_sync) >= 2:
        import statistics

        out_median = int(statistics.median([m.offset_ms for m in out_of_sync]))
        clustered_out = [m for m in out_of_sync if abs(m.offset_ms - out_median) <= 300]
        if len(clustered_out) / len(out_of_sync) >= 0.80:
            first_affected = min(clustered_out, key=lambda m: m.cue.start_ms).cue
            after_cue = first_affected.model_copy()
            after_cue.start_ms = out_median  # Store shift amount in metadata
            return Fix(
                id="FIX_GLOBAL_SHIFT",
                finding_ids=[f.id for f in alignment.findings if f.code == "SYNC_OFFSET"],
                type="global_shift",
                before=first_affected.model_copy(),
                after=after_cue,
                auto=True,
                status="proposed",
            )

    return None


def plan_fix_normalize_tag(finding: Finding, cue: Cue) -> Optional[Fix]:
    """Convert parentheses around sound tag to brackets, or pair music notes."""
    text = cue.text
    # (SOUND) -> [SOUND]
    new_text = re.sub(r"\(([A-Za-z\s]+)\)", r"[\1]", text)
    if "♪" in new_text and new_text.count("♪") % 2 != 0:
        new_text = new_text.strip() + " ♪"

    if new_text != text:
        after_cue = cue.model_copy()
        after_cue.lines = new_text.split("\n")
        after_cue.raw_text = new_text
        return Fix(
            id=f"FIX_{finding.id}",
            finding_ids=[finding.id],
            type="normalize_tag",
            before=cue.model_copy(),
            after=after_cue,
            auto=True,
            status="proposed",
        )
    return None


def plan_fix_prepend_speaker(
    finding: Finding, cue: Cue, speaker_label: str
) -> Fix:
    """Prepend speaker identification label to cue text."""
    label = speaker_label.upper()
    after_cue = cue.model_copy()
    if after_cue.lines:
        after_cue.lines[0] = f"{label}: {after_cue.lines[0]}"
    else:
        after_cue.lines = [f"{label}: {cue.raw_text}"]
    after_cue.raw_text = "\n".join(after_cue.lines)

    return Fix(
        id=f"FIX_{finding.id}",
        finding_ids=[finding.id],
        type="prepend_speaker",
        before=cue.model_copy(),
        after=after_cue,
        auto=True,
        status="proposed",
    )


def plan_fix_insert_tag(
    finding: Finding, t_ms: int, label: str
) -> Fix:
    """Insert a new bracketed SDH sound effect cue."""
    clean_label = label if label.startswith("[") else f"[{label}]"
    new_cue = Cue(
        index=0,  # Will be renumbered on insertion
        start_ms=t_ms,
        end_ms=t_ms + 1500,
        lines=[clean_label],
        raw_text=clean_label,
        kind="caption",
    )
    return Fix(
        id=f"FIX_{finding.id}",
        finding_ids=[finding.id],
        type="insert_tag_cue",
        before=None,
        after=new_cue,
        auto=True,
        status="proposed",
    )


def plan_fix_retime_ad(
    finding: Finding,
    ad_cue: Cue,
    segments: List[Segment],
    profile: Profile,
) -> Fix:
    """Retime AD cue into nearest preceding or following dialogue silence."""
    duration = ad_cue.duration_ms
    min_gap = profile.min_gap_ms.value
    sorted_segs = sorted(segments, key=lambda s: s.start_ms)

    best_start: Optional[int] = None
    min_distance = float("inf")

    # Check silence before first segment
    if sorted_segs and sorted_segs[0].start_ms >= duration + min_gap:
        silence_start = 0
        silence_end = sorted_segs[0].start_ms - min_gap
        if silence_end - silence_start >= duration:
            dist = abs(silence_start - ad_cue.start_ms)
            if dist < min_distance:
                min_distance = dist
                best_start = silence_start

    # Check silences between segments
    for i in range(len(sorted_segs) - 1):
        silence_start = sorted_segs[i].end_ms + min_gap
        silence_end = sorted_segs[i + 1].start_ms - min_gap
        if silence_end - silence_start >= duration:
            dist = abs(silence_start - ad_cue.start_ms)
            if dist < min_distance:
                min_distance = dist
                best_start = silence_start

    if best_start is not None:
        after_ad = ad_cue.model_copy()
        after_ad.start_ms = best_start
        after_ad.end_ms = best_start + duration
        return Fix(
            id=f"FIX_{finding.id}",
            finding_ids=[finding.id],
            type="retime_ad",
            before=ad_cue.model_copy(),
            after=after_ad,
            auto=True,
            status="proposed",
        )

    # If no silence fits, mark manual
    return Fix(
        id=f"FIX_{finding.id}",
        finding_ids=[finding.id],
        type="manual",
        before=ad_cue.model_copy(),
        after=ad_cue.model_copy(),
        auto=False,
        status="proposed",
    )


def plan_fixes(
    findings: List[Finding],
    cues: List[Cue],
    profile: Profile,
    alignment: Optional[AlignmentResult] = None,
    ad_cues: Optional[List[Cue]] = None,
) -> List[Fix]:
    """Generate deterministic fix proposals for all actionable findings."""
    fixes: List[Fix] = []
    cue_map: Dict[int, Cue] = {c.index: c for c in cues}
    ad_map: Dict[int, Cue] = {c.index: c for c in (ad_cues or [])}

    # Check for global shift first
    if alignment:
        global_fix = plan_fix_global_shift(alignment, cues, profile)
        if global_fix:
            fixes.append(global_fix)

    for f in findings:
        cue = cue_map.get(f.cue_index) if f.cue_index is not None else None
        next_cue = None
        if cue:
            for c in cues:
                if c.start_ms > cue.start_ms:
                    if next_cue is None or c.start_ms < next_cue.start_ms:
                        next_cue = c

        if f.code == "EMPTY" and cue:
            fixes.append(plan_fix_empty(f, cue))

        elif f.code in ("GAP_MIN", "OVERLAP") and cue and next_cue:
            fix = plan_fix_trim(f, cue, next_cue, profile)
            if fix:
                fixes.append(fix)

        elif f.code == "DUR_MIN" and cue:
            fix = plan_fix_extend(f, cue, next_cue, profile)
            if fix:
                fixes.append(fix)

        elif f.code == "CPS" and cue:
            # First try extend into gap
            fix = plan_fix_extend(f, cue, next_cue, profile)
            if fix:
                fixes.append(fix)
            else:
                # Else try split
                split_res = plan_fix_split(f, cue, profile)
                if split_res:
                    c1, c2 = split_res
                    fixes.append(
                        Fix(
                            id=f"FIX_{f.id}",
                            finding_ids=[f.id],
                            type="split",
                            before=cue.model_copy(),
                            after=c1,
                            after_extra=c2,
                            auto=True,
                            status="proposed",
                        )
                    )
                else:
                    fixes.append(
                        Fix(
                            id=f"FIX_{f.id}",
                            finding_ids=[f.id],
                            type="manual",
                            before=cue.model_copy(),
                            after=cue.model_copy(),
                            auto=False,
                            status="proposed",
                        )
                    )

        elif f.code in ("CPL", "LINES") and cue:
            fix = plan_fix_rewrap(f, cue, profile)
            if fix:
                fixes.append(fix)

        elif f.code == "TAG_FORMAT" and cue:
            fix = plan_fix_normalize_tag(f, cue)
            if fix:
                fixes.append(fix)

        elif f.code == "SDH_MISSING_SFX":
            tag_label = f.evidence.split("'")[1] if "'" in f.evidence else "[SOUND]"
            fix = plan_fix_insert_tag(f, f.start_ms, tag_label)
            fixes.append(fix)

        elif f.code == "SDH_MISSING_SPEAKER_ID" and cue:
            # Extract speaker name from evidence if present
            m_label = re.search(r"Speaker '([^']+)'", f.evidence)
            speaker = m_label.group(1) if m_label else "SPEAKER"
            fixes.append(plan_fix_prepend_speaker(f, cue, speaker))

        elif f.code == "MISSING_DIALOGUE" and alignment:
            unmatched = next(
                (s for s in alignment.unmatched_segments if s.start_ms == f.start_ms),
                None,
            )
            if unmatched:
                min_dur = profile.min_duration_ms.value
                end_ms = max(unmatched.end_ms, unmatched.start_ms + min_dur)
                inserted = Cue(
                    index=0,
                    start_ms=unmatched.start_ms,
                    end_ms=end_ms,
                    lines=[unmatched.text],
                    raw_text=unmatched.text,
                    kind="caption",
                )
                fixes.append(
                    Fix(
                        id=f"FIX_{f.id}",
                        finding_ids=[f.id],
                        type="insert_dialogue",
                        before=None,
                        after=inserted,
                        auto=True,
                        status="proposed",
                    )
                )

        elif f.code == "ACCURACY_LOW" and cue and alignment:
            pair = next(
                (m for m in alignment.matches if m.cue.index == cue.index),
                None,
            )
            if pair:
                after_cue = cue.model_copy()
                after_cue.lines = [pair.segment.text]
                after_cue.raw_text = pair.segment.text
                fixes.append(
                    Fix(
                        id=f"FIX_{f.id}",
                        finding_ids=[f.id],
                        type="replace_text",
                        before=cue.model_copy(),
                        after=after_cue,
                        auto=True,
                        status="proposed",
                    )
                )

        elif f.code == "AD_OVERLAPS_DIALOGUE" and f.cue_index:
            ad_cue = ad_map.get(f.cue_index)
            if ad_cue and alignment:
                all_segs = [p.segment for p in alignment.matches] + alignment.unmatched_segments
                fixes.append(plan_fix_retime_ad(f, ad_cue, all_segs, profile))

    # Link fix_id back onto findings
    fix_id_map = {}
    for fix in fixes:
        for fid in fix.finding_ids:
            fix_id_map[fid] = fix.id

    for f in findings:
        if f.id in fix_id_map:
            f.fix_id = fix_id_map[f.id]

    return fixes


def apply_accepted_fixes(
    cues: List[Cue],
    fixes: List[Fix],
    ad_cues: Optional[List[Cue]] = None,
    median_shift_ms: int = 0,
) -> Tuple[List[Cue], List[Cue]]:
    """Regenerate cues and AD scripts from the accepted set of fixes."""
    accepted = [f for f in fixes if f.status == "accepted"]
    if not accepted:
        return list(cues), list(ad_cues or [])

    new_cues: List[Cue] = []
    has_global_shift = any(f.type == "global_shift" for f in accepted)
    inserted_tags: List[Cue] = []

    # Map cue replacements
    cue_after_map: Dict[int, Optional[Cue]] = {}
    for fix in accepted:
        if fix.type == "global_shift":
            continue
        if fix.type in ("insert_tag_cue", "insert_dialogue") and fix.after:
            inserted_tags.append(fix.after)
            if fix.after_extra:
                inserted_tags.append(fix.after_extra)
        elif fix.type == "split" and fix.before and fix.before.kind == "caption":
            cue_after_map[fix.before.index] = fix.after
            if fix.after_extra:
                inserted_tags.append(fix.after_extra)
        elif fix.before and fix.before.kind == "caption":
            cue_after_map[fix.before.index] = fix.after

    for orig_cue in cues:
        if orig_cue.index in cue_after_map:
            replacement = cue_after_map[orig_cue.index]
            if replacement is not None:
                new_cues.append(replacement.model_copy())
            # None means deleted
        else:
            new_cues.append(orig_cue.model_copy())

    new_cues.extend(inserted_tags)

    # If global shift accepted, shift cues from first affected cue onward
    global_fix = next((f for f in accepted if f.type == "global_shift"), None)
    if global_fix and global_fix.before:
        first_ms = global_fix.before.start_ms
        shift = global_fix.after.start_ms if global_fix.after else median_shift_ms
        for c in new_cues:
            if c.start_ms >= first_ms:
                c.start_ms -= shift
                c.end_ms -= shift
    elif has_global_shift and median_shift_ms != 0:
        for c in new_cues:
            c.start_ms -= median_shift_ms
            c.end_ms -= median_shift_ms

    # Sort and renumber
    new_cues.sort(key=lambda c: c.start_ms)
    for i, c in enumerate(new_cues, start=1):
        c.index = i

    # Process AD cues
    new_ad: List[Cue] = []
    ad_after_map: Dict[int, Optional[Cue]] = {
        fix.before.index: fix.after
        for fix in accepted
        if fix.before and fix.before.kind == "ad"
    }
    for ad in (ad_cues or []):
        if ad.index in ad_after_map:
            repl = ad_after_map[ad.index]
            if repl is not None:
                new_ad.append(repl.model_copy())
        else:
            new_ad.append(ad.model_copy())

    new_ad.sort(key=lambda c: c.start_ms)
    for i, c in enumerate(new_ad, start=1):
        c.index = i

    return new_cues, new_ad
