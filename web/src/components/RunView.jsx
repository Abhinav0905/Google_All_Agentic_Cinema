import { useMemo, useRef, useState } from "react";
import {
  Check,
  Download,
  Pause,
  Play,
  X,
} from "lucide-react";
import { msToTimecode, seekSeconds } from "../timecode.js";
import { api } from "../api.js";

const STEPS = [
  { id: "ingest", label: "Ingest" },
  { id: "transcribe", label: "Transcribe" },
  { id: "listen", label: "Listen" },
  { id: "look", label: "Look" },
  { id: "rules", label: "Rules" },
  { id: "align", label: "Align" },
  { id: "semantic", label: "Semantic" },
  { id: "score_and_plan", label: "Score" },
];

const SEV = {
  error: "bg-error/15 text-red-300",
  warning: "bg-warn/15 text-amber-300",
  info: "bg-info/20 text-slate-300",
};

const DIM_COPY = {
  accuracy: "Accuracy",
  synchronicity: "Synchronicity",
  completeness: "Completeness",
  readability: "Readability",
  sdh_coverage: "SDH coverage",
  ad_coverage: "AD coverage",
};

function statusColor(status) {
  if (status === "pass") return "text-pass";
  if (status === "warn") return "text-warn";
  if (status === "fail") return "text-error";
  return "text-bay-500";
}

function stepRecord(run, id) {
  return (run.steps || []).find((s) => s.step_name === id);
}

function Scorecard({ scorecard }) {
  if (!scorecard) {
    return (
      <div className="rounded-xl border border-bay-700 bg-bay-850 p-6 text-sm text-bay-500">
        Scorecard appears when the pipeline finishes.
      </div>
    );
  }
  const dims = [
    "accuracy",
    "synchronicity",
    "completeness",
    "readability",
    "sdh_coverage",
    "ad_coverage",
  ];
  return (
    <div>
      <div className="mb-3 flex items-baseline justify-between">
        <h2 className="text-sm font-semibold uppercase tracking-wider text-bay-500">
          Scorecard
        </h2>
        <span className={`tc text-xs font-semibold ${statusColor(scorecard.overall_status)}`}>
          {scorecard.overall_status.toUpperCase()}
        </span>
      </div>
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
        {dims.map((key) => {
          const dim = scorecard[key];
          if (!dim) return null;
          return (
            <div key={key} className="rounded-xl border border-bay-700 bg-bay-850 p-4">
              <div className="text-xs uppercase tracking-wider text-bay-500">
                {DIM_COPY[key]}
              </div>
              <div className={`tc mt-2 text-2xl font-semibold ${statusColor(dim.status)}`}>
                {(dim.score * 100).toFixed(1)}%
              </div>
              <div className="tc mt-1 text-[11px] text-bay-500">
                spec {(dim.threshold * 100).toFixed(0)}% · {dim.status}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function VideoBay({ run, selected, seekRef, videoFile }) {
  const videoRef = useRef(null);
  const [playing, setPlaying] = useState(false);
  const [now, setNow] = useState(0);
  const durationMs = useMemo(() => {
    const last = Math.max(
      60_000,
      ...(run.findings || []).map((f) => f.end_ms || 0),
      ...(run.cues || []).map((c) => c.end_ms || 0),
    );
    return last;
  }, [run]);

  const objectUrl = useMemo(
    () => (videoFile ? URL.createObjectURL(videoFile) : null),
    [videoFile],
  );

  const seekTo = (ms) => {
    const t = seekSeconds(ms);
    if (videoRef.current && videoRef.current.duration) {
      videoRef.current.currentTime = t;
    }
    setNow(t * 1000);
  };
  if (seekRef) seekRef.current = seekTo;

  const markers = run.findings || [];

  return (
    <div className="overflow-hidden rounded-xl border border-bay-700 bg-black">
      <div className="relative aspect-video bg-[#07080c]">
        {objectUrl || run.media_url ? (
          <video
            ref={videoRef}
            className="h-full w-full object-contain"
            src={objectUrl || run.media_url}
            onTimeUpdate={(e) => setNow(e.currentTarget.currentTime * 1000)}
            onPlay={() => setPlaying(true)}
            onPause={() => setPlaying(false)}
            onError={() => {
              /* sample clip may be absent; synthetic rail still seeks */
            }}
          />
        ) : null}
        <div className="pointer-events-none absolute inset-0 flex flex-col justify-between p-4">
          <div className="text-[11px] uppercase tracking-[0.2em] text-bay-500">Picture</div>
          <div className="tc text-3xl font-medium text-white/90 drop-shadow">
            {msToTimecode(now)}
          </div>
        </div>
      </div>
      <div className="border-t border-bay-800 bg-bay-900 px-4 py-3">
        <div className="relative h-8">
          <div className="absolute inset-x-0 top-3 h-px bg-bay-700" />
          {markers.map((f) => (
            <button
              key={f.id}
              type="button"
              title={f.code}
              onClick={() => seekTo(f.start_ms)}
              className={`absolute top-1.5 h-4 w-1.5 rounded-sm ${
                f.severity === "error"
                  ? "bg-error"
                  : f.severity === "warning"
                    ? "bg-warn"
                    : "bg-slate-400"
              } ${selected?.id === f.id ? "ring-2 ring-white" : ""}`}
              style={{ left: `${Math.min(98, (f.start_ms / durationMs) * 100)}%` }}
            />
          ))}
        </div>
        <div className="mt-2 flex items-center justify-between text-xs text-bay-500">
          <button
            type="button"
            className="inline-flex items-center gap-1 text-bay-300"
            onClick={() => {
              const el = videoRef.current;
              if (el && el.duration) {
                if (el.paused) el.play();
                else el.pause();
              }
            }}
          >
            {playing ? <Pause className="h-3.5 w-3.5" /> : <Play className="h-3.5 w-3.5" />}
            {playing ? "Pause" : "Play"}
          </button>
          <span className="tc">{msToTimecode(durationMs)}</span>
        </div>
      </div>
    </div>
  );
}

function FindingDrawer({ run, finding, onClose, onSeek, onDecide }) {
  if (!finding) return null;
  const cue = (run.cues || []).find((c) => c.index === finding.cue_index);
  const fix = (run.fixes || []).find((f) => f.id === finding.fix_id);
  return (
    <aside className="flex h-full flex-col border-l border-bay-700 bg-bay-850">
      <div className="flex items-center justify-between border-b border-bay-700 px-5 py-4">
        <div>
          <div className="tc text-xs text-accent">{finding.code}</div>
          <button
            type="button"
            className="seek-link tc mt-1 text-sm"
            onClick={() => onSeek(finding.start_ms)}
          >
            {msToTimecode(finding.start_ms)}
          </button>
        </div>
        <button type="button" onClick={onClose} className="text-bay-500 hover:text-white">
          <X className="h-4 w-4" />
        </button>
      </div>
      <div className="flex-1 space-y-5 overflow-y-auto px-5 py-5 text-sm">
        <p>{finding.message}</p>
        {cue && (
          <div>
            <div className="mb-1 text-xs uppercase tracking-wider text-bay-500">Cue</div>
            <pre className="whitespace-pre-wrap rounded-md bg-bay-900 p-3 text-bay-300">
              {cue.text}
            </pre>
          </div>
        )}
        {finding.evidence && (
          <div>
            <div className="mb-1 text-xs uppercase tracking-wider text-bay-500">Evidence</div>
            <p className="text-bay-300">{finding.evidence}</p>
          </div>
        )}
        {finding.spec_ref && (
          <div>
            <div className="mb-1 text-xs uppercase tracking-wider text-bay-500">Spec</div>
            <p className="text-accent/80">{finding.spec_ref}</p>
          </div>
        )}
        {fix && (
          <div>
            <div className="mb-2 text-xs uppercase tracking-wider text-bay-500">
              Proposed fix · {fix.type} · {fix.status}
            </div>
            <div className="grid gap-3 md:grid-cols-2">
              <div className="rounded-md border border-error/20 bg-error/5 p-3">
                <div className="mb-1 text-[11px] uppercase text-red-300">Before</div>
                <div className="tc text-[11px] text-bay-500">
                  {fix.before
                    ? `${msToTimecode(fix.before.start_ms)} → ${msToTimecode(fix.before.end_ms)}`
                    : "—"}
                </div>
                <pre className="mt-2 whitespace-pre-wrap text-xs">
                  {fix.before?.raw_text || fix.before?.lines?.join("\n") || "[insert]"}
                </pre>
              </div>
              <div className="rounded-md border border-pass/20 bg-pass/5 p-3">
                <div className="mb-1 text-[11px] uppercase text-emerald-300">After</div>
                <div className="tc text-[11px] text-bay-500">
                  {fix.after
                    ? `${msToTimecode(fix.after.start_ms)} → ${msToTimecode(fix.after.end_ms)}`
                    : "[delete]"}
                </div>
                <pre className="mt-2 whitespace-pre-wrap text-xs">
                  {fix.after?.raw_text || fix.after?.lines?.join("\n") || ""}
                </pre>
              </div>
            </div>
            <div className="mt-4 flex gap-2">
              <button
                type="button"
                onClick={() => onDecide(fix.id, "accept")}
                className="inline-flex items-center gap-1 rounded-md bg-pass/20 px-3 py-1.5 text-xs font-semibold text-emerald-200"
              >
                <Check className="h-3.5 w-3.5" /> Accept
              </button>
              <button
                type="button"
                onClick={() => onDecide(fix.id, "reject")}
                className="inline-flex items-center gap-1 rounded-md bg-error/20 px-3 py-1.5 text-xs font-semibold text-red-200"
              >
                <X className="h-3.5 w-3.5" /> Reject
              </button>
            </div>
          </div>
        )}
      </div>
    </aside>
  );
}

export default function RunView({ run, videoFile, onRunChange, onBack }) {
  const [selectedId, setSelectedId] = useState(null);
  const [codeFilter, setCodeFilter] = useState("all");
  const [sevFilter, setSevFilter] = useState("all");
  const seekRef = useRef(null);

  const selected = (run.findings || []).find((f) => f.id === selectedId) || null;
  const codes = [...new Set((run.findings || []).map((f) => f.code))].sort();
  const findings = (run.findings || [])
    .filter((f) => (codeFilter === "all" ? true : f.code === codeFilter))
    .filter((f) => (sevFilter === "all" ? true : f.severity === sevFilter))
    .sort((a, b) => a.start_ms - b.start_ms);

  const seek = (ms) => {
    seekRef.current?.(ms);
  };

  const openFinding = (f) => {
    setSelectedId(f.id);
    seek(f.start_ms);
  };

  const decide = async (fixId, decision) => {
    const next = await api.decideFix(run.id, fixId, decision);
    onRunChange(next);
  };

  return (
    <div className="flex min-h-[calc(100vh-56px)]">
      <aside className="w-64 shrink-0 border-r border-bay-800 bg-bay-900/60 p-4">
        <button type="button" onClick={onBack} className="mb-4 text-xs text-bay-500 hover:text-white">
          ← New QC
        </button>
        <div className="text-xs uppercase tracking-wider text-bay-500">Pipeline</div>
        <ol className="mt-3 space-y-2">
          {STEPS.map((step, idx) => {
            const rec = stepRecord(run, step.id);
            const status = rec?.status || (run.status === "pending" ? "pending" : "pending");
            return (
              <li key={step.id} className="rounded-lg border border-bay-800 bg-bay-850 px-3 py-2">
                <div className="flex items-center justify-between">
                  <span className="text-sm">
                    <span className="tc mr-2 text-[11px] text-bay-500">{idx + 1}</span>
                    {step.label}
                  </span>
                  <span
                    className={`tc text-[10px] ${
                      status === "completed"
                        ? "text-pass"
                        : status === "running"
                          ? "text-accent"
                          : status === "failed"
                            ? "text-error"
                            : "text-bay-500"
                    }`}
                  >
                    {status.toUpperCase()}
                  </span>
                </div>
                {rec?.duration_s ? (
                  <div className="tc mt-1 text-[10px] text-bay-500">{rec.duration_s}s</div>
                ) : null}
                {rec?.summary ? (
                  <div className="mt-1 line-clamp-2 text-[11px] text-bay-500">{rec.summary}</div>
                ) : (
                  <div className="mt-1 text-[11px] text-bay-700">Waiting</div>
                )}
              </li>
            );
          })}
        </ol>
      </aside>

      <main className="min-w-0 flex-1 overflow-y-auto p-6">
        {run.status === "failed" && (
          <div className="mb-4 rounded-lg border border-error/40 bg-error/10 px-4 py-3 text-sm text-red-200">
            Pipeline failed. {(run.steps || []).find((s) => s.status === "failed")?.summary}
          </div>
        )}
        {run.status === "running" && !run.scorecard && (
          <div className="mb-4 rounded-lg border border-accent/30 bg-accent/10 px-4 py-3 text-sm text-indigo-100">
            Running the eight-step bay…
          </div>
        )}

        <Scorecard scorecard={run.scorecard} />

        <div className="mt-8">
          <h2 className="mb-3 text-sm font-semibold uppercase tracking-wider text-bay-500">
            Timeline
          </h2>
          <VideoBay
            run={run}
            selected={selected}
            videoFile={videoFile}
            seekRef={seekRef}
          />
        </div>

        <div className="mt-8">
          <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
            <h2 className="text-sm font-semibold uppercase tracking-wider text-bay-500">
              Findings
            </h2>
            <div className="flex gap-2">
              <select
                value={codeFilter}
                onChange={(e) => setCodeFilter(e.target.value)}
                className="rounded-md border border-bay-700 bg-bay-900 px-2 py-1 text-xs"
              >
                <option value="all">All codes</option>
                {codes.map((c) => (
                  <option key={c} value={c}>
                    {c}
                  </option>
                ))}
              </select>
              <select
                value={sevFilter}
                onChange={(e) => setSevFilter(e.target.value)}
                className="rounded-md border border-bay-700 bg-bay-900 px-2 py-1 text-xs"
              >
                <option value="all">All severities</option>
                <option value="error">Error</option>
                <option value="warning">Warning</option>
                <option value="info">Info</option>
              </select>
            </div>
          </div>
          <div className="overflow-hidden rounded-xl border border-bay-700">
            <table className="w-full text-left text-sm">
              <thead className="bg-bay-900 text-[11px] uppercase tracking-wider text-bay-500">
                <tr>
                  <th className="px-4 py-3">Time</th>
                  <th className="px-4 py-3">Sev</th>
                  <th className="px-4 py-3">Code</th>
                  <th className="px-4 py-3">Message</th>
                </tr>
              </thead>
              <tbody>
                {run.status === "completed" && findings.length === 0 && (
                  <tr>
                    <td colSpan={4} className="px-4 py-8 text-center text-bay-500">
                      No findings for this filter.
                    </td>
                  </tr>
                )}
                {run.status !== "completed" && (
                  <tr>
                    <td colSpan={4} className="px-4 py-8 text-center text-bay-500">
                      Findings will list here when scoring finishes.
                    </td>
                  </tr>
                )}
                {findings.map((f) => (
                  <tr
                    key={f.id}
                    onClick={() => openFinding(f)}
                    className={`cursor-pointer border-t border-bay-800 hover:bg-bay-800/60 ${
                      selectedId === f.id ? "bg-bay-800" : ""
                    }`}
                  >
                    <td className="px-4 py-3">
                      <button
                        type="button"
                        className="seek-link tc text-xs"
                        onClick={(e) => {
                          e.stopPropagation();
                          openFinding(f);
                        }}
                      >
                        {msToTimecode(f.start_ms)}
                      </button>
                    </td>
                    <td className="px-4 py-3">
                      <span className={`rounded px-2 py-0.5 text-[10px] uppercase ${SEV[f.severity]}`}>
                        {f.severity}
                      </span>
                    </td>
                    <td className="tc px-4 py-3 text-xs">{f.code}</td>
                    <td className="px-4 py-3 text-bay-300">{f.message}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        {run.status === "completed" && (
          <div className="mt-8 rounded-xl border border-bay-700 bg-bay-850 p-5">
            <div className="mb-3 text-sm font-semibold uppercase tracking-wider text-bay-500">
              Apply and export
            </div>
            <p className="mb-4 text-sm text-bay-500">
              Accepted fixes are written into the export. Proposed and rejected items stay as they were.
            </p>
            <div className="flex flex-wrap gap-2">
              {["srt", "vtt", "json", "report"].map((fmt) => (
                <a
                  key={fmt}
                  href={api.exportUrl(run.id, fmt)}
                  className="inline-flex items-center gap-2 rounded-md border border-bay-700 px-3 py-2 text-xs font-semibold uppercase hover:border-accent/50"
                >
                  <Download className="h-3.5 w-3.5" />
                  {fmt}
                </a>
              ))}
            </div>
          </div>
        )}
      </main>

      {selected && (
        <div className="w-[380px] shrink-0">
          <FindingDrawer
            run={run}
            finding={selected}
            onClose={() => setSelectedId(null)}
            onSeek={seek}
            onDecide={decide}
          />
        </div>
      )}
    </div>
  );
}
