async function parseJson(res) {
  const text = await res.text();
  let data = {};
  if (text) {
    try {
      data = JSON.parse(text);
    } catch {
      data = {
        detail: text
      };
    }
  }
  if (!res.ok) {
    const detail = data.detail || res.statusText;
    throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
  }
  return data;
}
export const api = {
  health: () => fetch("/api/health").then(parseJson),
  listRuns: () => fetch("/api/runs").then(parseJson),
  createRun: (metadata = {}) => fetch("/api/runs", {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify(metadata)
  }).then(parseJson),
  startSample: body => fetch("/api/runs/sample", {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify(body || {
      profile_id: "adult",
      sdh_mode: true,
      has_ad: true
    })
  }).then(parseJson),
  startRun: (id, body) => fetch(`/api/runs/${id}/start`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify(body)
  }).then(parseJson),
  getRun: id => fetch(`/api/runs/${id}`).then(parseJson),
  decideFix: (runId, fixId, decision) => fetch(`/api/runs/${runId}/fixes/${fixId}`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify({
      decision
    })
  }).then(parseJson),
  uploadAssets: async (id, captionFile, adFile, videoFile) => {
    const form = new FormData();
    if (captionFile) form.append("captions", captionFile);
    if (adFile) form.append("ad", adFile);
    if (videoFile) form.append("video", videoFile);
    const res = await fetch(`/api/runs/${id}/assets`, {
      method: "POST",
      body: form
    });
    return parseJson(res);
  },
  exportUrl: (id, format) => `/api/runs/${id}/export?format=${format}`,
  mediaUrl: id => `/api/runs/${id}/media`
};
