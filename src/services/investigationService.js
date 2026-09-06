import mockInvestigations from "../data/mockInvestigation";

const investigations = new Map();

const investigationStages = [
  "starting",
  "dns",
  "http",
  "path_discovery",
  "path_analysis",
  "complete",
];

const scenarios = [
  "healthy",
  "pathDegradation",
  "highLatency",
  "packetLoss",
];

export function startInvestigation(target) {
  const investigationId = crypto.randomUUID();

  const scenarioName = chooseScenario(target);
  const scenario = mockInvestigations[scenarioName];

  const investigation = {
    ...scenario,
    id: investigationId,
    target,
    status: "starting",
    stageIndex: 0,
    createdAt: new Date().toISOString(),
  };

  investigations.set(investigationId, investigation);

  simulateInvestigation(investigationId);

  return investigationId;
}

export function getInvestigationStatus(investigationId) {
  const investigation = investigations.get(investigationId);

  if (!investigation) {
    throw new Error("Investigation not found");
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

  return investigation;
}

function chooseScenario(target) {
  const normalizedTarget = target.toLowerCase();

  if (normalizedTarget === "github.com") {
    return "pathDegradation";
  }

  if (normalizedTarget === "google.com") {
    return "highLatency";
  }

  if (normalizedTarget === "8.8.8.8") {
    return "packetLoss";
  }

  return scenarios[Math.floor(Math.random() * scenarios.length)];
}

function simulateInvestigation(investigationId) {
  const interval = setInterval(() => {
    const investigation = investigations.get(investigationId);

    if (!investigation) {
      clearInterval(interval);
      return;
    }

    if (investigation.stageIndex >= investigationStages.length - 1) {
      investigation.status = "complete";
      clearInterval(interval);
      return;
    }

    investigation.stageIndex += 1;
    investigation.status =
      investigationStages[investigation.stageIndex];
  }, 1500);
}