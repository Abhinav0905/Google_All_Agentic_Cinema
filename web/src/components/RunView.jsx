import { useEffect, useMemo, useRef, useState } from "react";
import { ArrowDownToLine, ArrowLeft, ArrowRight, Check, CheckCheck, ChevronDown, ChevronRight, CircleHelp, Film, ListChecks, LoaderCircle, Pause, Play, Volume2, VolumeX, X } from "lucide-react";
import { msToRange, msToTimecode, seekSeconds } from "../timecode.js";
import { api } from "../api.js";
const STEPS = [["ingest", "Read the files"], ["transcribe", "Map the dialogue"], ["listen", "Listen for sound"], ["look", "Look at the scene"], ["rules", "Check the captions"], ["align", "Compare the timing"], ["semantic", "Find missing context"], ["score_and_plan", "Prepare the review"]];
const DIMENSIONS = {
  accuracy: "Accuracy",
  synchronicity: "Timing",
  completeness: "Dialogue",
  readability: "Readability",
  sdh_coverage: "Sound & speakers",
  ad_coverage: "Description"
};
const TITLES = {
  SDH_MISSING_SFX: "A sound is missing",
  SDH_MISSING_SPEAKER_ID: "Who's speaking?",
  MISSING_DIALOGUE: "Dialogue without a caption",
  ACCURACY_LOW: "The words don't match",
  SYNC_OFFSET: "Caption timing is off",
  EXTRA_CAPTION: "An unmatched caption",
  AD_GAP: "A visual moment is missing",
  AD_ONSCREEN_TEXT: "On-screen text needs context",
  AD_OVERLAPS_DIALOGUE: "Description overlaps dialogue",
  AD_READING_RATE: "Description needs more time",
  EMPTY: "An empty caption",
  ORDER: "Captions out of sequence",
  DUR_MIN: "Gone too quickly",
  DUR_MAX: "On screen too long",
  CPS: "Too much to read",
  CPL: "A line runs long",
  LINES: "Too many lines",
  OVERLAP: "Captions overlap",
  GAP_MIN: "A little breathing room",
  TAG_FORMAT: "Check the sound label"
};
const modeCopy = {
  sample: {
    label: "Sample review",
    text: "Reference audio and visual annotations power this sample. The rule checks, decisions and exports run here; no live model analysis is claimed."
  },
  live: {
    label: "Live media analysis",
    text: "This review uses your media with the connected analysis service. Check each finding against the picture and sound before approving a change."
  },
  caption_only: {
    label: "Caption-only review",
    text: "Timing and readability checks are available. Audio, dialogue accuracy and visual coverage were not analyzed. Any uploaded video is available for playback."
  }
};
const shortTime = ms => msToTimecode(ms).slice(3, 8);
const percent = score => `${Math.round(score * 100)}%`;
function QualityStrip({
  scorecard,
  after,
  running
}) {
  return <section className="quality-section" aria-label="Quality scorecard">
    <div className="quality-heading"><span className="eyebrow">QUALITY AT A GLANCE</span><span>{after ? "Original → approved edits" : running ? "Review in progress" : "Against the selected profile"}</span></div>
    <div className="quality-strip">{Object.entries(DIMENSIONS).map(([key, label]) => {
        const dim = scorecard?.[key];
        const next = after?.[key];
        return <div className="quality-dimension" key={key}><span>{label}</span><div className={`quality-number ${next?.status || dim?.status || "unknown"}`}>{dim ? <>{after && next ? <><span className="previous-score">{percent(dim.score)}</span><ArrowRight size={12} />{percent(next.score)}</> : percent(dim.score)}</> : running ? <span className="score-loading" /> : "—"}</div><small>{dim ? `Target ${percent(dim.threshold)}` : running ? "Checking" : "Not assessed"}</small></div>;
      })}</div>
  </section>;
}
function VideoBay({
  run,
  selected,
  seekRef,
  videoFile,
  onSelect
}) {
  const videoRef = useRef(null);
  const [playing, setPlaying] = useState(false);
  const [muted, setMuted] = useState(false);
  const [now, setNow] = useState(0);
  const [mediaFailed, setMediaFailed] = useState(false);
  const [mediaDuration, setMediaDuration] = useState(0);
  const [showCaptions, setShowCaptions] = useState(true);
  const objectUrl = useMemo(() => videoFile ? URL.createObjectURL(videoFile) : null, [videoFile]);
  useEffect(() => () => {
    if (objectUrl) URL.revokeObjectURL(objectUrl);
  }, [objectUrl]);
  const src = objectUrl || run.media_url;
  useEffect(() => {
    setMediaFailed(false);
    setPlaying(false);
    setNow(0);
    setMediaDuration(0);
  }, [src]);
  const duration = mediaDuration || Math.max(1000, ...(run.findings || []).map(f => f.end_ms || 0), ...(run.cues || []).map(c => c.end_ms || 0));
  const hasMedia = Boolean(src && !mediaFailed);
  const seekTo = (ms, preRoll = true) => {
    const seconds = preRoll ? seekSeconds(ms) : Math.max(0, ms / 1000);
    if (videoRef.current && Number.isFinite(videoRef.current.duration)) videoRef.current.currentTime = Math.min(seconds, videoRef.current.duration);
    setNow(seconds * 1000);
  };
  seekRef.current = seekTo;
  const cue = (run.cues || []).filter(item => item.start_ms <= now && item.end_ms > now);
  const togglePlay = () => {
    const el = videoRef.current;
    if (!el || !hasMedia) return;
    if (el.paused) el.play().catch(() => setPlaying(false));else el.pause();
  };
  return <section className="video-bay" aria-label="Video review player">
    <div className="player-topline"><span><span className="tiny-square" /> PICTURE MONITOR</span><span>{videoFile?.name || (run.analysis_mode === "sample" ? "The Briefing" : "Review picture")}</span></div>
    <div className="picture">
      {hasMedia ? <video ref={videoRef} src={src} playsInline preload="metadata" muted={muted} onTimeUpdate={e => setNow(e.currentTarget.currentTime * 1000)} onLoadedMetadata={e => setMediaDuration(e.currentTarget.duration * 1000)} onPlay={() => setPlaying(true)} onPause={() => setPlaying(false)} onEnded={() => setPlaying(false)} onError={() => setMediaFailed(true)} aria-label="Uploaded film" /> : <div className="picture-empty"><Film size={34} strokeWidth={1} /><h3>{mediaFailed ? "Picture unavailable" : "A review without picture"}</h3><p>{mediaFailed ? "The video couldn't be loaded. You can still review the caption findings below." : "This review has no saved video. Caption findings and exports are still available."}</p></div>}
      {hasMedia && !playing && <button className="picture-play" onClick={togglePlay} aria-label="Play film"><Play size={25} fill="currentColor" /></button>}
      {hasMedia && showCaptions && cue.length > 0 && <div className="caption-overlay">{cue.map(c => <span key={c.index}>{c.text || c.raw_text || c.lines?.join("\n")}</span>)}</div>}
    </div>
    <div className="player-controls"><button className="player-icon" onClick={togglePlay} disabled={!hasMedia} aria-label={playing ? "Pause film" : "Play film"}>{playing ? <Pause size={17} /> : <Play size={17} />}</button><span className="tc player-clock">{shortTime(now)} <span>/ {shortTime(duration)}</span></span><input className="playback-slider" type="range" aria-label="Video position" min="0" max={duration} value={Math.min(now, duration)} step="100" onChange={e => seekTo(Number(e.target.value), false)} disabled={!hasMedia} /><button className={`cc-button ${showCaptions ? "active" : ""}`} aria-label={showCaptions ? "Hide original captions" : "Show original captions"} aria-pressed={showCaptions} onClick={() => setShowCaptions(!showCaptions)}>CC</button><button className="player-icon" onClick={() => setMuted(!muted)} disabled={!hasMedia} aria-label={muted ? "Unmute film" : "Mute film"}>{muted ? <VolumeX size={17} /> : <Volume2 size={17} />}</button></div>
    <div className="finding-timeline"><div className="timeline-label"><span>FINDINGS IN THE CUT</span><span>Click a marker to review</span></div><div className="timeline-track"><div className="track-line" />{(run.findings || []).map((f, i) => <button key={f.id} className={`timeline-marker ${f.severity} ${selected?.id === f.id ? "selected" : ""}`} style={{
          left: `${Math.min(97, Math.max(1, f.start_ms / duration * 100))}%`,
          top: `${8 + i % 2 * 13}px`
        }} title={`${shortTime(f.start_ms)} · ${TITLES[f.code] || f.code}`} aria-label={`Review ${TITLES[f.code] || f.code} at ${shortTime(f.start_ms)}`} onClick={() => {
          onSelect(f);
          seekTo(f.start_ms);
        }} />)}</div><div className="timeline-ticks"><span>00:00</span><span>{shortTime(duration / 3)}</span><span>{shortTime(duration * 2 / 3)}</span><span>{shortTime(duration)}</span></div></div>
    <div className="player-footnote">Original captions in the player. Approved changes appear in your export.</div>
  </section>;
}
function FindingDetail({
  run,
  finding,
  onClose,
  onSeek,
  onDecide,
  deciding
}) {
  if (!finding) return <div className="detail-empty"><CircleHelp size={24} strokeWidth={1.25} /><h3>Take a closer look.</h3><p>Select a finding to see the evidence and review a proposed correction.</p></div>;
  const cue = (run.cues || []).find(c => c.index === finding.cue_index);
  const fix = (run.fixes || []).find(f => f.id === finding.fix_id);
  const beforeText = fix?.before?.raw_text || fix?.before?.lines?.join("\n");
  const afterText = fix?.after?.raw_text || fix?.after?.lines?.join("\n");
  return <section className="finding-detail" aria-label="Selected finding">
    <div className="detail-heading"><div><span className={`severity-label ${finding.severity}`}>{finding.severity === "error" ? "Needs attention" : finding.severity === "warning" ? "Worth a look" : "For review"}</span><h3 tabIndex={-1}>{TITLES[finding.code] || finding.code.replaceAll("_", " ")}</h3></div><button className="icon-button" aria-label="Close finding details" onClick={onClose}><X size={18} /></button></div>
    <button className="detail-time tc" onClick={() => onSeek(finding.start_ms)}><Play size={12} />{msToRange(finding.start_ms, finding.end_ms)}</button>
    <p className="finding-explanation">{finding.message}</p>
    {finding.evidence && <div className="evidence-block"><span className="eyebrow">{run.analysis_mode === "sample" ? "REFERENCE EVIDENCE" : "EVIDENCE"}</span><p>{finding.evidence}</p></div>}
    {fix ? <><div className="correction-pair"><div className="correction before"><span className="eyebrow">ORIGINAL</span><p>{beforeText || (fix.before ? "Empty caption" : "New caption cue")}</p>{fix.before && <small className="tc">{msToRange(fix.before.start_ms, fix.before.end_ms)}</small>}</div><div className="correction after"><span className="eyebrow">PROPOSED EDIT</span><p>{afterText || (fix.after ? "Empty caption" : "Remove this caption")}</p>{fix.after && <small className="tc">{msToRange(fix.after.start_ms, fix.after.end_ms)}</small>}</div></div><div className="decision-actions"><button className={`button ${fix.status === "accepted" ? "accepted-button" : "primary"}`} disabled={Boolean(deciding) || fix.status === "accepted"} onClick={() => onDecide(fix.id, "accept")}>{deciding === `${fix.id}:accept` ? <LoaderCircle size={15} className="spin" /> : <Check size={16} />} {fix.status === "accepted" ? "Approved for export" : "Approve edit"}</button><button className="button secondary" disabled={Boolean(deciding) || fix.status === "rejected"} onClick={() => onDecide(fix.id, "reject")}>{fix.status === "rejected" ? <Check size={15} /> : <X size={15} />} {fix.status === "rejected" ? "Original kept" : "Keep original"}</button></div></> : <><div className="correction before"><span className="eyebrow">CURRENT CAPTION</span><p>{cue?.text || cue?.raw_text || cue?.lines?.join("\n") || "No caption at this moment"}</p></div><p className="manual-note">This finding needs an editorial decision. No automatic edit is proposed.</p></>}
    {finding.spec_ref && <details className="spec-details"><summary>Rule reference <ChevronDown size={13} /></summary><p>{finding.spec_ref}</p><code>{finding.code}</code></details>}
  </section>;
}
function Pipeline({
  run
}) {
  const completed = (run.steps || []).filter(s => s.status === "completed").length;
  return <details className="pipeline"><summary><span><ListChecks size={18} /> Behind the review <small>{completed} / {STEPS.length} steps</small></span><ChevronDown size={16} /></summary><p className="pipeline-note">{run.analysis_mode === "sample" ? "Sample annotations are prewritten references. The steps below show the actual local processing of that fixture." : "The processing record for this review. Expand a step to inspect its result."}</p><ol>{STEPS.map(([id, title], i) => {
        const step = (run.steps || []).find(s => s.step_name === id);
        return <li key={id}><details><summary><span className="step-index">{String(i + 1).padStart(2, "0")}</span><span>{title}</span><span className={`step-status ${step?.status || "pending"}`}>{step?.status === "running" && <LoaderCircle className="spin" size={11} />} {step?.status || "pending"}</span></summary><p>{step?.summary || "Waiting for this step."}{step?.duration_s ? ` (${step.duration_s}s)` : ""}</p></details></li>;
      })}</ol></details>;
}
export default function RunView({
  run,
  videoFile,
  onRunChange,
  onBack
}) {
  const [selectedId, setSelectedId] = useState(null);
  const [sevFilter, setSevFilter] = useState("all");
  const [error, setError] = useState("");
  const [deciding, setDeciding] = useState("");
  const [exporting, setExporting] = useState("");
  const [exported, setExported] = useState("");
  const seekRef = useRef(null);
  const sidebarRef = useRef(null);
  useEffect(() => {
    const sidebar = sidebarRef.current;
    if (!sidebar) return;
    if (!selectedId) {
      sidebar.scrollTop = 0;
      return;
    }
    const frame = requestAnimationFrame(() => {
      const detail = sidebar.querySelector(".finding-detail");
      if (!detail) return;
      detail.querySelector("h3")?.focus({
        preventScroll: true
      });
      if (window.matchMedia("(min-width: 781px)").matches) {
        sidebar.scrollTop += detail.getBoundingClientRect().top - sidebar.getBoundingClientRect().top - 8;
      } else detail.scrollIntoView({
        block: "start",
        behavior: "auto"
      });
    });
    return () => cancelAnimationFrame(frame);
  }, [selectedId]);
  const running = ["pending", "running"].includes(run.status);
  const selected = (run.findings || []).find(f => f.id === selectedId) || null;
  const allFindings = [...(run.findings || [])].sort((a, b) => a.start_ms - b.start_ms);
  const findings = allFindings.filter(f => sevFilter === "all" || f.severity === sevFilter);
  const accepted = (run.fixes || []).filter(f => f.status === "accepted").length;
  const mode = modeCopy[run.analysis_mode] || {
    label: "Review",
    text: "Inspect the evidence and processing record before approving changes."
  };
  const seek = ms => seekRef.current?.(ms);
  const select = f => {
    setSelectedId(f.id);
    seek(f.start_ms);
  };
  const decide = async (fixId, decision) => {
    setError("");
    setDeciding(`${fixId}:${decision}`);
    setExported("");
    try {
      onRunChange(await api.decideFix(run.id, fixId, decision));
    } catch (err) {
      setError(err.message || "Couldn't save that decision. Please try again.");
    } finally {
      setDeciding("");
    }
  };
  const exportFile = async format => {
    setError("");
    setExporting(format);
    try {
      const res = await fetch(api.exportUrl(run.id, format));
      if (!res.ok) {
        const message = await res.json().catch(() => ({}));
        throw new Error(message.detail || "The export could not be prepared.");
      }
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = `framekind-${run.id.slice(0, 8)}.${format === "report" ? "html" : format}`;
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
      onRunChange(await api.getRun(run.id));
      setExported(format.toUpperCase());
    } catch (err) {
      setError(err.message);
    } finally {
      setExporting("");
    }
  };
  return <main id="main-content" className="review-page">
    <div className="review-heading"><div><button className="back-link" onClick={onBack}><ArrowLeft size={14} /> Back to workspace</button><div className="review-title"><h1>{run.analysis_mode === "sample" ? "The Briefing" : "A closer look."}</h1><span className={`mode-badge ${run.analysis_mode || ""}`}><span />{mode.label}</span></div></div><div className="review-meta"><span>{run.profile_id === "kids" ? "Children's profile" : "Adult broadcast"}</span><small className="tc">REVIEW / {run.id.slice(0, 8).toUpperCase()}</small></div></div>
    <div className={`review-notice ${running ? "is-running" : ""}`} role="status">{running ? <LoaderCircle size={16} className="spin" /> : <CircleHelp size={16} />}<span>{running ? `Review in progress. ${mode.text}` : mode.text}</span></div>
    {run.status === "failed" && <div className="alert" role="alert">The review stopped. {(run.steps || []).find(s => s.status === "failed")?.summary || "Open the processing record for details."}</div>}
    {error && <div className="alert" role="alert">{error}</div>}
    <div className="review-grid"><div className="review-main"><VideoBay {...{
          run,
          selected,
          seekRef,
          videoFile
        }} onSelect={select} /><QualityStrip scorecard={run.scorecard} after={run.after_scorecard} running={running} />
      {run.status === "completed" && <section className="export-section"><div className="export-heading"><span className="export-icon"><CheckCheck size={23} /></span><div><h2>Your decisions. Ready to go.</h2><p>{accepted} {accepted === 1 ? "edit" : "edits"} approved. Only approved changes are applied.</p></div></div><div className="export-actions">{["srt", "vtt", "json", "report"].map(format => <button key={format} className={`button ${format === "srt" ? "primary" : "secondary"}`} disabled={Boolean(exporting) || Boolean(deciding)} onClick={() => exportFile(format)}>{exporting === format ? <LoaderCircle size={15} className="spin" /> : <ArrowDownToLine size={15} />} {format === "report" ? "Review report" : format.toUpperCase()}</button>)}</div>{exported && <p className="export-success" role="status"><Check size={14} />{exported} prepared. The score comparison reflects the approved edits.</p>}<p className="export-disclaimer">Scores support your review. They don't certify accessibility.</p></section>}
      <Pipeline run={run} />
    </div><aside ref={sidebarRef} className={`review-sidebar ${selectedId ? "has-selection" : ""}`} aria-label="Findings and corrections"><div className="findings-heading"><div><span className="eyebrow">THE REVIEW NOTES</span><h2>Worth a closer look. <span>{allFindings.length}</span></h2></div></div><div className="finding-filters" role="group" aria-label="Filter findings">{[["all", "All"], ["error", "Errors"], ["warning", "Warnings"], ["info", "Notes"]].map(([value, label]) => <button key={value} aria-pressed={sevFilter === value} className={sevFilter === value ? "active" : ""} onClick={() => setSevFilter(value)}>{label}{value === "all" ? ` ${allFindings.length}` : ""}</button>)}</div><div className="finding-list">{findings.length === 0 ? <div className="empty-findings">{running ? <><LoaderCircle size={20} className="spin" /><p>The review notes will arrive here.</p></> : <><Check size={20} /><p>No findings in this view.</p></>}</div> : findings.map(f => {
            const fix = (run.fixes || []).find(x => x.id === f.fix_id);
            return <button className={`finding-row ${selectedId === f.id ? "selected" : ""}`} key={f.id} onClick={() => select(f)}><span className={`finding-dot ${f.severity} ${fix?.status === "accepted" ? "resolved" : ""}`}>{fix?.status === "accepted" ? <Check size={10} /> : null}</span><span className="finding-row-copy"><strong>{TITLES[f.code] || f.code.replaceAll("_", " ")}</strong><span>{f.message}</span></span><span className="finding-row-time"><span className="tc">{shortTime(f.start_ms)}</span><ChevronRight size={14} /></span></button>;
          })}</div><FindingDetail run={run} finding={selected} onClose={() => setSelectedId(null)} onSeek={seek} onDecide={decide} deciding={deciding} /></aside></div>
  </main>;
}
