const investigations = new Map();

const investigationStages = [
  "starting",
  "dns",
  "http",
  "path_discovery",
  "path_analysis",
  "complete",
];

const API_BASE_URL = "http://127.0.0.1:8000";

export function startInvestigation(target) {
  const investigationId = crypto.randomUUID();

  const investigation = {
    id: investigationId,
    target,
    status: "starting",
    stageIndex: 0,
    createdAt: new Date().toISOString(),
    result: null,
    error: null,
    backendComplete: false,
  };

  investigations.set(investigationId, investigation);

  runBackendInvestigation(investigationId, target);
  simulateInvestigationStages(investigationId);

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

  if (!investigation.result) {
    throw new Error("Investigation result is not ready");
  }

  return investigation.result;
}

async function runBackendInvestigation(investigationId, target) {
  const investigation = investigations.get(investigationId);

  if (!investigation) {
    return;
  }

  try {
    const response = await fetch(`${API_BASE_URL}/investigate`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        target,
      }),
    });

    if (!response.ok) {
      let errorMessage = `Backend returned HTTP ${response.status}`;

      try {
        const errorData = await response.json();

        if (errorData?.detail) {
          errorMessage = errorData.detail;
        }
      } catch {
        // Keep the default HTTP error message.
      }

      throw new Error(errorMessage);
    }

    const result = await response.json();

    const currentInvestigation = investigations.get(investigationId);

    if (!currentInvestigation) {
      return;
    }

    currentInvestigation.result = result;
    currentInvestigation.backendComplete = true;

    if (
      currentInvestigation.stageIndex >=
      investigationStages.length - 1
    ) {
      currentInvestigation.status = "complete";
    }
  } catch (error) {
    const currentInvestigation = investigations.get(investigationId);

    if (!currentInvestigation) {
      return;
    }

    currentInvestigation.error =
      error instanceof Error
        ? error.message
        : "Unknown backend error";

    currentInvestigation.status = "error";
  }
}

function simulateInvestigationStages(investigationId) {
  const interval = setInterval(() => {
    const investigation = investigations.get(investigationId);

    if (!investigation) {
      clearInterval(interval);
      return;
    }

    if (investigation.status === "error") {
      clearInterval(interval);
      return;
    }

    if (
      investigation.stageIndex >=
      investigationStages.length - 1
    ) {
      if (investigation.backendComplete) {
        investigation.status = "complete";
        clearInterval(interval);
      }

      return;
    }

    investigation.stageIndex += 1;
    investigation.status =
      investigationStages[investigation.stageIndex];
  }, 1500);
}