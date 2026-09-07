const API_BASE = import.meta.env.VITE_API_BASE || "http://localhost:8000";

const investigations = new Map();

const investigationStages = [
  "starting",
  "dns",
  "http",
  "path_discovery",
  "path_analysis",
  "complete",
];

// The backend runs the whole pipeline synchronously and returns once, so
// this timer just advances the on-screen stage indicator while the real
// request (which can take a while -- traceroute alone can run for
// several seconds per hop) is in flight.
const STAGE_INTERVAL_MS = 900;

export function startInvestigation(target) {
  const investigationId = crypto.randomUUID();

  const investigation = {
    target,
    status: "starting",
    stageIndex: 0,
    result: null,
    error: null,
    createdAt: new Date().toISOString(),
  };

  investigations.set(investigationId, investigation);

  const stageTimer = setInterval(() => {
    if (
      investigation.status === "complete" ||
      investigation.status === "error"
    ) {
      clearInterval(stageTimer);
      return;
    }

    if (investigation.stageIndex < investigationStages.length - 2) {
      investigation.stageIndex += 1;
      investigation.status = investigationStages[investigation.stageIndex];
    }
  }, STAGE_INTERVAL_MS);

  fetch(`${API_BASE}/diagnose`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ target }),
  })
    .then(async (response) => {
      if (!response.ok) {
        const body = await response.json().catch(() => ({}));
        throw new Error(body.detail || `Request failed with status ${response.status}`);
      }
      return response.json();
    })
    .then((result) => {
      investigation.result = result;
      investigation.stageIndex = investigationStages.length - 1;
      investigation.status = "complete";
      clearInterval(stageTimer);
    })
    .catch((error) => {
      investigation.error = error.message;
      investigation.status = "error";
      clearInterval(stageTimer);
    });

  return investigationId;
}

export function getInvestigationStatus(investigationId) {
  const investigation = investigations.get(investigationId);

  if (!investigation) {
    throw new Error("Investigation not found");
  }

  if (investigation.status === "error") {
    throw new Error(investigation.error || "Investigation failed");
  }

  return {
    status: investigation.status,
    stage: investigationStages[investigation.stageIndex],
  };
}

export function getInvestigationResult(investigationId) {
  const investigation = investigations.get(investigationId);

  if (!investigation) {
    throw new Error("Investigation not found");
  }

  return investigation.result;
}
