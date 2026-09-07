import { useEffect, useRef, useState } from "react";
import { Clapperboard } from "lucide-react";
import { api } from "./api.js";
import NewQc from "./components/NewQc.jsx";
import RunView from "./components/RunView.jsx";

function subscribeEvents(runId, onEvent) {
  const source = new EventSource(`/api/runs/${runId}/events`);
  const handler = () => {
    api.getRun(runId).then(onEvent).catch(() => {});
  };
  source.addEventListener("trace", handler);
  source.addEventListener("run.complete", () => {
    handler();
    source.close();
  });
  source.addEventListener("run.failed", () => {
    handler();
    source.close();
  });
  source.onerror = () => {
    api.getRun(runId).then(onEvent).catch(() => {});
  };
  return source;
}

export default function App() {
  const [view, setView] = useState("new");
  const [health, setHealth] = useState(null);
  const [history, setHistory] = useState([]);
  const [run, setRun] = useState(null);
  const [videoFile, setVideoFile] = useState(null);
  const [captionFile, setCaptionFile] = useState(null);
  const [adFile, setAdFile] = useState(null);
  const [profileId, setProfileId] = useState("adult");
  const [sdhMode, setSdhMode] = useState(true);
  const [hasAd, setHasAd] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const sourceRef = useRef(null);

  const refreshHistory = () => api.listRuns().then(setHistory).catch(() => {});

  useEffect(() => {
    api.health().then(setHealth).catch(() => setHealth({ vertex: false, gcs: false }));
    refreshHistory();
    return () => sourceRef.current?.close();
  }, []);

  useEffect(() => {
    if (!run || run.status !== "running") return undefined;
    const timer = setInterval(() => {
      api.getRun(run.id).then(setRun).catch(() => {});
    }, 400);
    return () => clearInterval(timer);
  }, [run]);

  const watch = (runId) => {
    sourceRef.current?.close();
    sourceRef.current = subscribeEvents(runId, setRun);
  };

  const onSample = async () => {
    setBusy(true);
    setError("");
    try {
      const created = await api.startSample({
        profile_id: profileId,
        sdh_mode: sdhMode,
        has_ad: true,
      });
      setVideoFile(null);
      setRun(created);
      setView("run");
      watch(created.id);
      refreshHistory();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  };

  const onRun = async () => {
    setBusy(true);
    setError("");
    try {
      if (!captionFile) throw new Error("A caption file is required.");
      const created = await api.createRun();
      if (created.gcs_configured && created.uploads.captions.url) {
        const putText = async (file, slot) => {
          const res = await fetch(slot.url, {
            method: "PUT",
            headers: { "Content-Type": slot.content_type },
            body: file,
          });
          if (!res.ok) throw new Error(`Upload failed (${res.status})`);
        };
        await putText(captionFile, created.uploads.captions);
        if (hasAd && adFile) await putText(adFile, created.uploads.ad);
        if (videoFile && created.uploads.video.url) {
          const res = await fetch(created.uploads.video.url, {
            method: "PUT",
            headers: { "Content-Type": "video/mp4" },
            body: videoFile,
          });
          if (!res.ok) throw new Error(`Video upload failed (${res.status})`);
        }
      } else {
        await api.uploadAssets(created.id, captionFile, hasAd ? adFile : null);
      }
      const started = await api.startRun(created.id, {
        profile_id: profileId,
        sdh_mode: sdhMode,
        has_ad: Boolean(hasAd && adFile),
      });
      setRun(started);
      setView("run");
      watch(started.id);
      refreshHistory();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  };

  const openHistory = async (id) => {
    const next = await api.getRun(id);
    setRun(next);
    setView("run");
    if (next.status === "running") watch(id);
  };

  return (
    <div className="min-h-screen">
      <header className="flex items-center justify-between border-b border-bay-800 px-6 py-3">
        <div className="flex items-center gap-3">
          <Clapperboard className="h-5 w-5 text-accent" />
          <div>
            <div className="text-sm font-semibold tracking-wide">CueCheck</div>
            <div className="text-[11px] uppercase tracking-[0.18em] text-bay-500">
              Accessibility QC Bay
            </div>
          </div>
        </div>
        <nav className="flex items-center gap-4 text-xs uppercase tracking-wider text-bay-500">
          <button
            type="button"
            onClick={() => setView("new")}
            className={view === "new" ? "text-white" : "hover:text-white"}
          >
            New
          </button>
          <button
            type="button"
            onClick={() => {
              refreshHistory();
              setView("history");
            }}
            className={view === "history" ? "text-white" : "hover:text-white"}
          >
            History
          </button>
        </nav>
      </header>

      {view === "new" && (
        <NewQc
          health={health}
          profileId={profileId}
          setProfileId={setProfileId}
          sdhMode={sdhMode}
          setSdhMode={setSdhMode}
          hasAd={hasAd}
          setHasAd={setHasAd}
          videoFile={videoFile}
          setVideoFile={setVideoFile}
          captionFile={captionFile}
          setCaptionFile={setCaptionFile}
          adFile={adFile}
          setAdFile={setAdFile}
          busy={busy}
          error={error}
          onRun={onRun}
          onSample={onSample}
        />
      )}

      {view === "run" && run && (
        <RunView
          run={run}
          videoFile={videoFile}
          onRunChange={setRun}
          onBack={() => setView("new")}
        />
      )}

      {view === "history" && (
        <div className="mx-auto max-w-4xl px-6 py-10">
          <h1 className="text-2xl font-semibold">History</h1>
          <p className="mt-2 text-sm text-bay-500">
            In-memory for this process. Postgres arrives with the Replit handoff.
          </p>
          <div className="mt-6 overflow-hidden rounded-xl border border-bay-700">
            <table className="w-full text-left text-sm">
              <thead className="bg-bay-900 text-[11px] uppercase tracking-wider text-bay-500">
                <tr>
                  <th className="px-4 py-3">When</th>
                  <th className="px-4 py-3">Profile</th>
                  <th className="px-4 py-3">Status</th>
                  <th className="px-4 py-3">Findings</th>
                </tr>
              </thead>
              <tbody>
                {history.length === 0 && (
                  <tr>
                    <td colSpan={4} className="px-4 py-8 text-center text-bay-500">
                      No runs yet. Load the sample to create the first one.
                    </td>
                  </tr>
                )}
                {history.map((row) => (
                  <tr
                    key={row.id}
                    className="cursor-pointer border-t border-bay-800 hover:bg-bay-800/50"
                    onClick={() => openHistory(row.id)}
                  >
                    <td className="tc px-4 py-3 text-xs">{row.created_at}</td>
                    <td className="px-4 py-3">{row.profile_id}</td>
                    <td className="tc px-4 py-3 text-xs">{row.status}</td>
                    <td className="px-4 py-3">{row.finding_count}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
