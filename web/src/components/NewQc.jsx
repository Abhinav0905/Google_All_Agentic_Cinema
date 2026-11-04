import { ArrowRight, ArrowUpRight, Check, FileAudio, FileText, Film, LoaderCircle, Plus, Volume2 } from "lucide-react";
function FileField({
  label,
  hint,
  file,
  accept,
  onFile,
  icon: Icon,
  optional
}) {
  return <label className={`file-field ${file ? "has-file" : ""}`}>
    <input aria-label={`Choose ${label.toLowerCase()} file`} type="file" accept={accept} onChange={e => onFile(e.target.files?.[0] || null)} />
    <span className="file-icon"><Icon size={21} strokeWidth={1.5} /></span>
    <span className="file-copy"><strong>{label} {optional && <em>optional</em>}</strong><span>{file ? file.name : hint}</span></span>
    <span className="file-action">{file ? <Check size={18} /> : <Plus size={19} />}</span>
  </label>;
}
function SceneArtwork() {
  return <svg className="scene-artwork" viewBox="0 0 660 440" role="img" aria-label="Illustration of a quiet room at dusk with a lit doorway">
    <defs><linearGradient id="room" x2="1" y2="1"><stop stopColor="#232e2f" /><stop offset="1" stopColor="#101b1c" /></linearGradient><linearGradient id="light" x2="0" y2="1"><stop stopColor="#f8d398" /><stop offset="1" stopColor="#b57549" /></linearGradient><linearGradient id="floor" x2="0" y2="1"><stop stopColor="#253334" /><stop offset="1" stopColor="#182324" /></linearGradient><pattern id="grain" width="8" height="8" patternUnits="userSpaceOnUse"><circle cx="1" cy="1" r=".6" fill="#fff" opacity=".05" /></pattern></defs>
    <rect width="660" height="440" fill="url(#room)" /><path d="M0 300H660V440H0Z" fill="url(#floor)" /><path d="M0 301H660" stroke="#809084" strokeOpacity=".2" />
    <rect x="425" y="76" width="117" height="234" fill="#0d1718" /><rect x="431" y="81" width="103" height="225" fill="url(#light)" /><path d="m443 90 61 8v210l-61-1Z" fill="#536055" /><circle cx="491" cy="206" r="3" fill="#e3be7d" /><path d="m505 308 27-1 126 133H456Z" fill="#d6a56a" opacity=".13" />
    <rect x="96" y="88" width="159" height="108" fill="#162124" stroke="#4a5852" strokeWidth="7" /><path d="M104 181 141 129 177 162 221 116 248 149v38H104Z" fill="#50675e" /><circle cx="215" cy="117" r="15" fill="#c49a63" />
    <path d="M152 292h171l-11 13H139Z" fill="#9a7960" /><path d="M149 304v82m161-82v82" stroke="#493f34" strokeWidth="8" />
    <rect x="179" y="284" width="59" height="6" rx="1" fill="#d1bd8f" transform="rotate(-5 179 284)" /><path d="M277 278v-38" stroke="#778273" strokeWidth="3" /><path d="m256 240 11-26h19l13 26Z" fill="#be9660" /><ellipse cx="276" cy="284" rx="16" ry="4" fill="#756854" />
    <path d="M344 328c-7-32-7-63 6-90 12-23 40-21 47 3 6 19 6 42 1 70l-5 18Z" fill="#0c1719" /><circle cx="373" cy="208" r="19" fill="#0c1719" />
    <rect width="660" height="440" fill="url(#grain)" />
  </svg>;
}
export default function NewQc({
  health,
  profileId,
  setProfileId,
  sdhMode,
  setSdhMode,
  hasAd,
  setHasAd,
  videoFile,
  setVideoFile,
  captionFile,
  setCaptionFile,
  adFile,
  setAdFile,
  busy,
  error,
  onRun,
  onSample
}) {
  const live = Boolean(health?.vertex);
  return <main id="main-content" className="new-page">
    <section className="hero">
      <div className="hero-copy"><div className="eyebrow"><span /> THE ACCESSIBILITY REVIEW ROOM</div><h1>Every part<br />of the <em>story.</em></h1><p>A knock at the door. A voice off-screen. Make sure your captions carry the moments that matter.</p><button className="text-action" onClick={onSample} disabled={Boolean(busy)}>{busy === "sample" ? "Opening the review…" : "Step into a sample review"} {busy === "sample" ? <LoaderCircle className="spin" size={19} /> : <ArrowUpRight size={21} />}</button><div className="hero-fine">Find the gap. Review the evidence. Make the edit.</div></div>
      <div className="hero-visual"><div className="scene-topline"><span>FRAMEKIND / STUDY NO. 01</span><span>PICTURE · SOUND · WORDS</span></div><div className="scene-frame"><SceneArtwork /><span className="scene-time">00:00:18:04</span><div className="scene-caption"><Volume2 size={16} /><span>[a knock at the door]</span><span className="caption-plus">+</span></div><span className="art-caption">CONCEPT ILLUSTRATION</span></div><div className="scene-bottomline"><span>The smallest sound can change the story.</span><span className="scene-dots"><i /><i /><i /></span></div></div>
    </section>

    <section className="start-section" aria-labelledby="start-title">
      <div className="section-heading"><div><div className="eyebrow">YOUR NEXT CUT</div><h2 id="start-title">Bring your story in.</h2></div><span className="quiet-tag"><span className={`status-dot ${live ? "" : "amber"}`} />{health == null ? "Checking review service" : live ? "Multimodal review configured" : "Caption checks available"}</span></div>
      {error && <div className="alert" role="alert">{error}</div>}
      <div className="upload-grid">
        <FileField label="Your film" hint={`Choose an MP4 · up to ${health?.gcs ? 500 : Math.round((health?.inline_video_max_bytes || 14 * 1024 * 1024) / 1024 / 1024)} MB`} file={videoFile} accept="video/mp4,.mp4" onFile={setVideoFile} icon={Film} optional />
        <FileField label="Captions" hint="Choose SRT or WebVTT · up to 2 MB" file={captionFile} accept=".srt,.vtt" onFile={setCaptionFile} icon={FileText} />
        <FileField label="Audio description" hint="Add an SRT or WebVTT script" file={adFile} accept=".srt,.vtt" onFile={file => {
          setAdFile(file);
          setHasAd(Boolean(file));
        }} icon={FileAudio} optional />
      </div>
      <div className="review-options"><div className="option-fields"><label className="profile-label">Review profile<select value={profileId} onChange={e => setProfileId(e.target.value)}><option value="adult">Adult broadcast</option><option value="kids">Children's</option></select></label><label className="check-label"><input type="checkbox" checked={sdhMode} onChange={e => setSdhMode(e.target.checked)} /> Sound & speaker checks</label>{adFile && <label className="check-label"><input type="checkbox" checked={hasAd} onChange={e => setHasAd(e.target.checked)} /> Include description</label>}</div><button className="button primary" disabled={Boolean(busy) || !captionFile} onClick={onRun}>{busy === "upload" ? <LoaderCircle className="spin" size={17} /> : null}{busy === "upload" ? "Starting review…" : "Start review"}<ArrowRight size={18} /></button></div>
      <p className="upload-note">{live ? "Your video and captions are compared for review. You approve every correction before export." : "Custom uploads receive caption timing and readability checks. Audio and visual checks need the connected cloud service."} <span>Sample reviews use a labeled reference fixture.</span></p>
    </section>
    <div className="process-line"><span><b>01</b> Watch with context</span><span><b>02</b> Review each finding</span><span><b>03</b> Export approved changes</span><span className="process-last">Your editorial judgment stays in the frame.</span></div>
  </main>;
}
