const mockInvestigations = {
  healthy: {
    id: "mock-healthy",
    target: "github.com",
    timestamp: "2026-09-06T08:00:00Z",

    dns: {
      status: "completed",
      resolved: true,
      address: "140.82.112.3",
    },

    http: {
      status: "completed",
      reachable: true,
      responseTime: 42,
      statusCode: 200,
    },

    currentPath: [
      {
        hopNumber: 1,
        ip: "192.168.1.1",
        rtt: 2,
        packetLoss: 0,
        asn: null,
        network: "Local Network",
        status: "normal",
        anomaly: null,
        evidence: [],
      },
      {
        hopNumber: 2,
        ip: "10.20.0.1",
        rtt: 8,
        packetLoss: 0,
        asn: "AS64500",
        network: "Example ISP",
        status: "normal",
        anomaly: null,
        evidence: [],
      },
      {
        hopNumber: 3,
        ip: "203.0.113.10",
        rtt: 18,
        packetLoss: 0,
        asn: "AS64501",
        network: "Example Transit",
        status: "normal",
        anomaly: null,
        evidence: [],
      },
      {
        hopNumber: 4,
        ip: "203.0.113.20",
        rtt: 27,
        packetLoss: 0,
        asn: "AS64502",
        network: "Example Network",
        status: "normal",
        anomaly: null,
        evidence: [],
      },
      {
        hopNumber: 5,
        ip: "140.82.112.3",
        rtt: 42,
        packetLoss: 0,
        asn: "AS36459",
        network: "GitHub",
        status: "destination",
        anomaly: null,
        evidence: [],
      },
    ],

    previousPath: null,

    pathComparison: {
      status: "no_baseline",
      message: "NO BASELINE AVAILABLE",
      addedHops: [],
      removedHops: [],
      commonHops: [],
      divergencePoint: null,
    },

    performanceComparison: null,

    anomalies: [],

    evidence: [],

    hypotheses: [],

    diagnosis: {
      probableCause: "No significant network degradation observed.",
      confidence: "HIGH",
      supportingEvidence: [],
      alternativeHypotheses: [],
    },

    timeline: [
      {
        event: "Investigation started",
        status: "completed",
      },
      {
        event: "DNS resolved",
        status: "completed",
      },
      {
        event: "HTTP checked",
        status: "completed",
      },
      {
        event: "Path discovered",
        status: "completed",
      },
      {
        event: "Path analysis completed",
        status: "completed",
      },
    ],
  },

  pathDegradation: {
    id: "mock-path-degradation",
    target: "github.com",
    timestamp: "2026-09-06T08:10:00Z",

    dns: {
      status: "completed",
      resolved: true,
      address: "140.82.112.3",
    },

    http: {
      status: "completed",
      reachable: true,
      responseTime: 198,
      statusCode: 200,
    },

    currentPath: [
      {
        hopNumber: 1,
        ip: "192.168.1.1",
        rtt: 2,
        packetLoss: 0,
        asn: null,
        network: "Local Network",
        status: "normal",
        anomaly: null,
        evidence: [],
      },
      {
        hopNumber: 2,
        ip: "10.20.0.1",
        rtt: 9,
        packetLoss: 0,
        asn: "AS64500",
        network: "Example ISP",
        status: "normal",
        anomaly: null,
        evidence: [],
      },
      {
        hopNumber: 3,
        ip: "203.0.113.10",
        rtt: 19,
        packetLoss: 0,
        asn: "AS64501",
        network: "Example Transit",
        status: "normal",
        anomaly: null,
        evidence: [],
      },
      {
        hopNumber: 4,
        ip: "198.51.100.20",
        rtt: 27,
        packetLoss: 0,
        asn: "AS64503",
        network: "Example Transit",
        status: "normal",
        anomaly: null,
        evidence: [],
      },
      {
        hopNumber: 5,
        ip: "198.51.100.50",
        rtt: 184,
        packetLoss: 14,
        asn: "AS64504",
        network: "Example Network",
        status: "anomalous",
        anomaly: {
          type: "High latency and packet loss",
          severity: "high",
        },
        evidence: [
          "RTT increased from 27 ms to 184 ms",
          "Packet loss increased from 0% to 14%",
        ],
      },
      {
        hopNumber: 6,
        ip: "140.82.112.3",
        rtt: 198,
        packetLoss: 14,
        asn: "AS36459",
        network: "GitHub",
        status: "destination",
        anomaly: null,
        evidence: [
          "Destination remains reachable",
          "HTTP response time increased",
        ],
      },
    ],

    previousPath: [
      {
        hopNumber: 1,
        ip: "192.168.1.1",
        rtt: 2,
        packetLoss: 0,
      },
      {
        hopNumber: 2,
        ip: "10.20.0.1",
        rtt: 8,
        packetLoss: 0,
      },
      {
        hopNumber: 3,
        ip: "203.0.113.10",
        rtt: 18,
        packetLoss: 0,
      },
      {
        hopNumber: 4,
        ip: "203.0.113.20",
        rtt: 27,
        packetLoss: 0,
      },
      {
        hopNumber: 5,
        ip: "140.82.112.3",
        rtt: 42,
        packetLoss: 0,
      },
    ],

    pathComparison: {
      status: "path_change_with_performance_impact",
      message: "PATH CHANGE WITH PERFORMANCE IMPACT",
      addedHops: [
        "198.51.100.20",
        "198.51.100.50",
      ],
      removedHops: [
        "203.0.113.20",
      ],
      commonHops: [
        "192.168.1.1",
        "10.20.0.1",
        "203.0.113.10",
      ],
      divergencePoint: 4,
    },

    performanceComparison: {
      status: "degraded",

      previous: {
        rtt: 42,
        packetLoss: 0,
        httpResponseTime: 42,
        httpStatusCode: 200,
      },

      current: {
        rtt: 198,
        packetLoss: 14,
        httpResponseTime: 198,
        httpStatusCode: 200,
      },

      difference: {
        rtt: 156,
        packetLoss: 14,
        httpResponseTime: 156,
      },
    },

    anomalies: [
      {
        type: "Route change",
        location: "Hop 4",
        severity: "high",
        measurement: "Path diverged from previous investigation",
        evidence: [
          "Previous route used 203.0.113.20",
          "Current route uses 198.51.100.20",
        ],
      },
      {
        type: "High latency",
        location: "Hop 5",
        severity: "high",
        measurement: "184 ms RTT",
        evidence: [
          "RTT increased from 27 ms to 184 ms",
        ],
      },
      {
        type: "Packet loss",
        location: "Hop 5",
        severity: "high",
        measurement: "14% packet loss",
        evidence: [
          "Packet loss increased from 0% to 14%",
        ],
      },
    ],

    evidence: [
      "Route changed at Hop 4",
      "RTT increased from 42 ms to 198 ms",
      "Packet loss increased from 0% to 14%",
      "Destination remains reachable",
      "HTTP response time increased from 42 ms to 198 ms",
    ],

    hypotheses: [
      {
        type: "Inference",
        description: "The changed network path is associated with the observed degradation.",
        confidence: "HIGH",
        evidence: [
          "Path divergence occurred before the latency increase",
          "Packet loss appeared on the new path",
        ],
      },
      {
        type: "Alternative hypothesis",
        description: "Transient congestion may be contributing to the observed performance degradation.",
        confidence: "MEDIUM",
        evidence: [
          "Elevated RTT and packet loss were observed on the new route",
        ],
      },
    ],

    diagnosis: {
      probableCause: "PATH DEGRADATION",
      confidence: "HIGH",
      supportingEvidence: [
        "Route changed at Hop 4",
        "RTT increased significantly after path divergence",
        "Packet loss appeared on Hop 5",
        "Destination remains reachable",
      ],
      alternativeHypotheses: [
        "Transient network congestion",
      ],
    },

    timeline: [
      {
        event: "Investigation started",
        status: "completed",
      },
      {
        event: "DNS resolved",
        status: "completed",
      },
      {
        event: "HTTP checked",
        status: "completed",
      },
      {
        event: "Path discovered",
        status: "completed",
      },
      {
        event: "Path change detected",
        status: "completed",
      },
      {
        event: "Anomaly detected",
        status: "completed",
      },
      {
        event: "Path analysis completed",
        status: "completed",
      },
      {
        event: "Diagnosis generated",
        status: "completed",
      },
    ],
  },

  highLatency: {
    id: "mock-high-latency",
    target: "google.com",
    timestamp: "2026-09-06T08:20:00Z",

    dns: {
      status: "completed",
      resolved: true,
      address: "142.250.195.14",
    },

    http: {
      status: "completed",
      reachable: true,
      responseTime: 320,
      statusCode: 200,
    },

    currentPath: [
      {
        hopNumber: 1,
        ip: "192.168.1.1",
        rtt: 3,
        packetLoss: 0,
        asn: null,
        network: "Local Network",
        status: "normal",
        anomaly: null,
        evidence: [],
      },
      {
        hopNumber: 2,
        ip: "10.20.0.1",
        rtt: 10,
        packetLoss: 0,
        asn: "AS64500",
        network: "Example ISP",
        status: "normal",
        anomaly: null,
        evidence: [],
      },
      {
        hopNumber: 3,
        ip: "203.0.113.30",
        rtt: 25,
        packetLoss: 0,
        asn: "AS64501",
        network: "Example Transit",
        status: "normal",
        anomaly: null,
        evidence: [],
      },
      {
        hopNumber: 4,
        ip: "203.0.113.40",
        rtt: 310,
        packetLoss: 0,
        asn: "AS64502",
        network: "Example Network",
        status: "high_latency",
        anomaly: {
          type: "High latency",
          severity: "high",
        },
        evidence: [
          "RTT reached 310 ms",
        ],
      },
      {
        hopNumber: 5,
        ip: "142.250.195.14",
        rtt: 320,
        packetLoss: 0,
        asn: "AS15169",
        network: "Google",
        status: "destination",
        anomaly: null,
        evidence: [
          "Destination remains reachable",
        ],
      },
    ],

    previousPath: null,

    pathComparison: {
      status: "no_baseline",
      message: "NO BASELINE AVAILABLE",
      addedHops: [],
      removedHops: [],
      commonHops: [],
      divergencePoint: null,
    },

    performanceComparison: null,

    anomalies: [
      {
        type: "High latency",
        location: "Hop 4",
        severity: "high",
        measurement: "310 ms RTT",
        evidence: [
          "Latency is significantly elevated at Hop 4",
        ],
      },
    ],

    evidence: [
      "RTT reached 310 ms at Hop 4",
      "Destination remains reachable",
      "HTTP response time is 320 ms",
      "No packet loss observed",
    ],

    hypotheses: [
      {
        type: "Inference",
        description: "A high-latency segment exists before the destination.",
        confidence: "MEDIUM",
        evidence: [
          "RTT increased sharply at Hop 4",
        ],
      },
    ],

    diagnosis: {
      probableCause: "HIGH LATENCY ON NETWORK PATH",
      confidence: "MEDIUM",
      supportingEvidence: [
        "RTT reached 310 ms at Hop 4",
        "Destination remains reachable",
        "No packet loss observed",
      ],
      alternativeHypotheses: [
        "Transient congestion",
      ],
    },

    timeline: [
      {
        event: "Investigation started",
        status: "completed",
      },
      {
        event: "DNS resolved",
        status: "completed",
      },
      {
        event: "HTTP checked",
        status: "completed",
      },
      {
        event: "Path discovered",
        status: "completed",
      },
      {
        event: "Anomaly detected",
        status: "completed",
      },
      {
        event: "Diagnosis generated",
        status: "completed",
      },
    ],
  },

  packetLoss: {
    id: "mock-packet-loss",
    target: "8.8.8.8",
    timestamp: "2026-09-06T08:30:00Z",

    dns: {
      status: "completed",
      resolved: true,
      address: "8.8.8.8",
    },

    http: {
      status: "completed",
      reachable: true,
      responseTime: 110,
      statusCode: null,
    },

    currentPath: [
      {
        hopNumber: 1,
        ip: "192.168.1.1",
        rtt: 2,
        packetLoss: 0,
        asn: null,
        network: "Local Network",
        status: "normal",
        anomaly: null,
        evidence: [],
      },
      {
        hopNumber: 2,
        ip: "10.20.0.1",
        rtt: 8,
        packetLoss: 0,
        asn: "AS64500",
        network: "Example ISP",
        status: "normal",
        anomaly: null,
        evidence: [],
      },
      {
        hopNumber: 3,
        ip: "203.0.113.50",
        rtt: 21,
        packetLoss: 0,
        asn: "AS64501",
        network: "Example Transit",
        status: "normal",
        anomaly: null,
        evidence: [],
      },
      {
        hopNumber: 4,
        ip: "203.0.113.60",
        rtt: 96,
        packetLoss: 18,
        asn: "AS64505",
        network: "Example Network",
        status: "anomalous",
        anomaly: {
          type: "Packet loss",
          severity: "high",
        },
        evidence: [
          "18% packet loss observed",
        ],
      },
      {
        hopNumber: 5,
        ip: "8.8.8.8",
        rtt: 110,
        packetLoss: 12,
        asn: "AS15169",
        network: "Google Public DNS",
        status: "destination",
        anomaly: null,
        evidence: [
          "12% packet loss observed at destination",
        ],
      },
    ],

    previousPath: null,

    pathComparison: {
      status: "no_baseline",
      message: "NO BASELINE AVAILABLE",
      addedHops: [],
      removedHops: [],
      commonHops: [],
      divergencePoint: null,
    },

    performanceComparison: null,

    anomalies: [
      {
        type: "Packet loss",
        location: "Hop 4",
        severity: "high",
        measurement: "18% packet loss",
        evidence: [
          "Packet loss first appears at Hop 4",
        ],
      },
      {
        type: "Packet loss",
        location: "Destination",
        severity: "high",
        measurement: "12% packet loss",
        evidence: [
          "Packet loss remains observable at the destination",
        ],
      },
    ],

    evidence: [
      "18% packet loss observed at Hop 4",
      "12% packet loss observed at destination",
      "RTT increased to 110 ms",
      "Destination remains reachable",
    ],

    hypotheses: [
      {
        type: "Inference",
        description: "Packet loss is present on the network path and affects destination reachability quality.",
        confidence: "HIGH",
        evidence: [
          "Packet loss first appears at Hop 4",
          "Packet loss remains visible at the destination",
        ],
      },
    ],

    diagnosis: {
      probableCause: "PACKET LOSS ON NETWORK PATH",
      confidence: "HIGH",
      supportingEvidence: [
        "18% packet loss observed at Hop 4",
        "12% packet loss observed at destination",
        "Destination remains reachable",
      ],
      alternativeHypotheses: [
        "Transient network congestion",
      ],
    },

    timeline: [
      {
        event: "Investigation started",
        status: "completed",
      },
      {
        event: "DNS resolved",
        status: "completed",
      },
      {
        event: "HTTP checked",
        status: "completed",
      },
      {
        event: "Path discovered",
        status: "completed",
      },
      {
        event: "Packet loss detected",
        status: "completed",
      },
      {
        event: "Diagnosis generated",
        status: "completed",
      },
    ],
  },
};

export default mockInvestigations;