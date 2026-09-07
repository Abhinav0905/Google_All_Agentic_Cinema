import { FileAudio, FileText, Film, Play, Sparkles } from "lucide-react";

function DropZone({ label, hint, file, accept, onFile, icon: Icon }) {
  return (
    <label className="block cursor-pointer rounded-xl border border-dashed border-bay-700 bg-bay-850/80 p-5 transition hover:border-accent/60 hover:bg-bay-800">
      <div className="flex items-start gap-3">
        <Icon className="mt-0.5 h-5 w-5 text-accent" />
        <div>
          <div className="text-sm font-semibold">{label}</div>
          <div className="mt-1 text-xs text-bay-500">{hint}</div>
          <div className="tc mt-3 text-xs text-bay-300">
            {file ? file.name : "No file selected"}
          </div>
        </div>
      </div>
      <input
        type="file"
        accept={accept}
        className="hidden"
        onChange={(e) => onFile(e.target.files?.[0] || null)}
      />
    </label>
  );
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
  onSample,
}) {
  return (
    <div className="mx-auto max-w-5xl px-6 py-10">
      <div className="mb-8">
        <div className="text-xs uppercase tracking-[0.2em] text-accent">New QC</div>
        <h1 className="mt-2 text-3xl font-semibold tracking-tight">
          Check a cut against the spec
        </h1>
        <p className="mt-3 max-w-2xl text-sm leading-6 text-bay-500">
          First time here? Click <span className="text-bay-300">Load sample</span>.
          No files, no cloud keys. The seeded captions already contain the defects
          the demo is meant to find.
        </p>
      </div>

      {error && (
        <div className="mb-6 rounded-lg border border-error/40 bg-error/10 px-4 py-3 text-sm text-red-200">
          {error}
        </div>
      )}

      <div className="grid gap-4 md:grid-cols-3">
        <DropZone
          label="Picture"
          hint="MP4, max 500 MB. Used for playback and seeking."
          file={videoFile}
          accept="video/mp4,video/*"
          onFile={setVideoFile}
          icon={Film}
        />
        <DropZone
          label="Captions"
          hint="SRT or WebVTT, max 2 MB."
          file={captionFile}
          accept=".srt,.vtt,text/plain"
          onFile={setCaptionFile}
          icon={FileText}
        />
        <DropZone
          label="Audio description"
          hint="Optional AD script."
          file={adFile}
          accept=".srt,.vtt,text/plain"
          onFile={setAdFile}
          icon={FileAudio}
        />
      </div>

      <div className="mt-8 grid gap-6 rounded-xl border border-bay-700 bg-bay-850 p-5 md:grid-cols-[1fr_auto] md:items-center">
        <div className="flex flex-wrap items-center gap-6">
          <label className="text-sm">
            <div className="mb-2 text-xs uppercase tracking-wider text-bay-500">Profile</div>
            <select
              value={profileId}
              onChange={(e) => setProfileId(e.target.value)}
              className="rounded-md border border-bay-700 bg-bay-900 px-3 py-2 text-sm"
            >
              <option value="adult">Adult broadcast</option>
              <option value="kids">Children&apos;s</option>
            </select>
          </label>
          <label className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={sdhMode}
              onChange={(e) => setSdhMode(e.target.checked)}
            />
            SDH checks
          </label>
          <label className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={hasAd}
              onChange={(e) => setHasAd(e.target.checked)}
            />
            AD script provided
          </label>
        </div>
        <div className="flex flex-wrap gap-3">
          <button
            type="button"
            disabled={busy}
            onClick={onSample}
            className="inline-flex items-center gap-2 rounded-md border border-bay-700 bg-bay-800 px-4 py-2 text-sm font-medium hover:border-accent/50 disabled:opacity-50"
          >
            <Sparkles className="h-4 w-4" />
            {busy ? "Loading sample…" : "Load sample"}
          </button>
          <button
            type="button"
            disabled={busy || !captionFile}
            onClick={onRun}
            className="inline-flex items-center gap-2 rounded-md bg-accent px-4 py-2 text-sm font-semibold text-bay-950 hover:bg-indigo-300 disabled:opacity-40"
          >
            <Play className="h-4 w-4" />
            {busy ? "Starting…" : "Run QC"}
          </button>
        </div>
      </div>

      <div className="mt-6 flex flex-wrap gap-6 text-xs text-bay-500">
        {health == null ? (
          <span className="tc">CHECKING SERVICES…</span>
        ) : (
          <>
            <span className="tc">VERTEX {health.vertex ? "READY" : "OFFLINE"}</span>
            <span className="tc">GCS {health.gcs ? "READY" : "LOCAL MODE"}</span>
            <span className="tc">STT {health.stt ? "ON" : "OFF"}</span>
          </>
        )}
      </div>
      {health && !health.gcs && (
        <p className="mt-3 text-xs text-bay-500">
          Local mode: picture stays in the browser. Caption and AD files are stored
          on this machine only. Vertex is optional for the sample.
        </p>
      )}
    </div>
  );
}
