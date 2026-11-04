import { useEffect, useRef, useState } from "react";
import { ArrowUpRight, Plus, Clock3 } from "lucide-react";
import { api } from "./api.js";
import { formatStamp } from "./timecode.js";
import NewQc from "./components/NewQc.jsx";
import RunView from "./components/RunView.jsx";
function FrameMark() {
  return <svg viewBox="0 0 36 36" fill="none" aria-hidden="true"><path d="M13 4H4v9M23 4h9v9M32 23v9h-9M13 32H4v-9" stroke="currentColor" strokeWidth="3" /><path d="m15 12 10 6-10 6V12Z" fill="currentColor" /></svg>;
}
function subscribeEvents(runId, onEvent) {
  const source = new EventSource(`/api/runs/${runId}/events`);
  const handler = () => api.getRun(runId).then(onEvent).catch(() => {});
  source.addEventListener("trace", handler);
  for (const event of ["run.complete", "run.failed"]) source.addEventListener(event, () => {
    handler();
    source.close();
  });
  source.onerror = handler;
  return source;
}
export default function App() {
  const [view, setView] = useState("new");
  const [health, setHealth] = useState(null);
  const [history, setHistory] = useState([]);
  const [run, setRun] = useState(null);
  const [videoFile, setVideoFile] = useState(null);
  const [runVideoFile, setRunVideoFile] = useState(null);
  const [captionFile, setCaptionFile] = useState(null);
  const [adFile, setAdFile] = useState(null);
  const [profileId, setProfileId] = useState("adult");
  const [sdhMode, setSdhMode] = useState(true);
  const [hasAd, setHasAd] = useState(false);
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");
  const [apiDown, setApiDown] = useState(false);
  const sourceRef = useRef(null);
  const refreshHistory = () => api.listRuns().then(setHistory).catch(() => {});
  useEffect(() => {
    api.health().then(h => {
      setHealth(h);
      setApiDown(false);
    }).catch(() => {
      setHealth({
        vertex: false,
        gcs: false,
        stt: false
      });
      setApiDown(true);
    });
    refreshHistory();
    return () => sourceRef.current?.close();
  }, []);
  useEffect(() => {
    if (!run || !["pending", "running"].includes(run.status)) return undefined;
    const timer = setInterval(() => api.getRun(run.id).then(setRun).catch(() => {}), 1500);
    return () => clearInterval(timer);
  }, [run?.id, run?.status]);
  const watch = runId => {
    sourceRef.current?.close();
    sourceRef.current = subscribeEvents(runId, setRun);
  };
  const onSample = async () => {
    setBusy("sample");
    setError("");
    try {
      const created = await api.startSample({
        profile_id: profileId,
        sdh_mode: sdhMode,
        has_ad: true
      });
      setRunVideoFile(null);
      setRun(created);
      setView("run");
      watch(created.id);
      refreshHistory();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy("");
    }
  };
  const onRun = async () => {
    setBusy("upload");
    setError("");
    try {
      if (!captionFile) throw new Error("Choose a caption file to start your review.");
      const videoLimit = health?.gcs ? 500 * 1024 * 1024 : health?.inline_video_max_bytes || 14 * 1024 * 1024;
      if (videoFile?.size > videoLimit) throw new Error(`Please choose a video smaller than ${Math.round(videoLimit / 1024 / 1024)} MB for this upload mode.`);
      if (captionFile.size > 2 * 1024 * 1024 || adFile?.size > 2 * 1024 * 1024) throw new Error("Caption and audio-description files must be smaller than 2 MB.");
      const created = await api.createRun({
        captions_size_bytes: captionFile.size,
        video_size_bytes: videoFile?.size || null,
        ad_size_bytes: hasAd && adFile ? adFile.size : null
      });
      if (created.gcs_configured && created.uploads.captions.url) {
        const put = async (file, slot) => {
          if (!slot?.url) throw new Error("An upload link is unavailable. Please start a new review.");
          const res = await fetch(slot.url, {
            method: "PUT",
            headers: {
              "Content-Type": slot.content_type
            },
            body: file
          });
          if (!res.ok) throw new Error(`Upload failed (${res.status}). Please try again.`);
        };
        await put(captionFile, created.uploads.captions);
        if (hasAd && adFile) await put(adFile, created.uploads.ad);
        if (videoFile) await put(videoFile, created.uploads.video);
      } else await api.uploadAssets(created.id, captionFile, hasAd ? adFile : null, videoFile);
      const started = await api.startRun(created.id, {
        profile_id: profileId,
        sdh_mode: sdhMode,
        has_ad: Boolean(hasAd && adFile)
      });
      setRunVideoFile(videoFile);
      setRun(started);
      setView("run");
      watch(started.id);
      refreshHistory();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy("");
    }
  };
  const openHistory = async id => {
    setError("");
    try {
      sourceRef.current?.close();
      const next = await api.getRun(id);
      setRunVideoFile(null);
      setRun(next);
      setView("run");
      if (["pending", "running"].includes(next.status)) watch(id);
    } catch (err) {
      setError(err.message);
    }
  };
  return <div className="app-shell">
    <a className="skip-link" href="#main-content">Skip to content</a>
    <header className="site-header">
      <button className="brand" onClick={() => setView("new")} aria-label="FrameKind home"><FrameMark /><span>Frame<span className="brand-kind">Kind</span><small>EVERY PART OF THE STORY.</small></span></button>
      <nav className="main-nav" aria-label="Main navigation">
        <button onClick={() => setView("new")} aria-current={view === "new" ? "page" : undefined}><Plus size={15} /> New review</button>
        <button onClick={() => {
          refreshHistory();
          setView("history");
        }} aria-current={view === "history" ? "page" : undefined}><Clock3 size={15} /> Review library</button>
      </nav>
      <div className="header-note"><span className={`status-dot ${apiDown ? "offline" : ""}`} />{apiDown ? "Service unavailable" : "Accessibility, in the edit."}</div>
    </header>
    {apiDown && <div className="service-alert" role="status">We can't reach the review service. Please try again in a moment.</div>}
    {view === "new" && <NewQc {...{
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
    }} />}
    {view === "run" && run && <RunView key={run.id} run={run} videoFile={runVideoFile} onRunChange={setRun} onBack={() => setView("new")} />}
    {view === "history" && <main id="main-content" className="library-page">
      <div className="eyebrow">YOUR WORKSPACE</div><h1>The review library.</h1><p className="muted">Pick up where you left off. Your findings, decisions and exports live here.</p>
      {error && <div className="alert" role="alert">{error}</div>}
      <div className="library-list">
        {history.length === 0 ? <div className="empty-library"><Clock3 size={32} /><h2>A little quiet here.</h2><p>Start with the sample scene, or bring a cut of your own.</p><button className="button primary" onClick={() => setView("new")}>Start your first review <ArrowUpRight size={17} /></button></div> : history.map((row, i) => <button className="library-row" key={row.id} onClick={() => openHistory(row.id)}><span className="library-index">{String(history.length - i).padStart(2, "0")}</span><span><strong>{row.analysis_mode === "sample" ? "The Briefing · Sample" : row.analysis_mode === "live" ? "Media review" : "Caption review"}</strong><small>{formatStamp(row.created_at)} · {row.profile_id === "kids" ? "Children's profile" : "Adult broadcast"}</small></span><span className={`status-label ${row.status}`}>{row.status}</span><span className="library-count">{row.finding_count} findings</span><ArrowUpRight size={19} /></button>)}
      </div>
    </main>}
    <footer className="site-footer"><span>Made for stories. Built for more people.</span><span>FrameKind <span className="footer-cross">+</span> Human review, always.</span></footer>
  </div>;
}
