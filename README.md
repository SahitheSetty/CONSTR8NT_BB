# BLACK BOX — Network Data Collector

## Overview

This module is the **Network Data Collection layer** of BLACK BOX, an Adaptive Network Investigation / Network Forensics platform.

Its responsibility is:

> **OBSERVE → MEASURE → RETURN RAW EVIDENCE**

The collector gathers network measurements for a user-provided target and returns structured evidence for the analysis and diagnosis layers.

## Responsibilities

The Network Data Collector gathers:

- DNS resolution information
- HTTP/service response information
- Network path using traceroute/tracert
- Investigation metadata
- Collection errors and measurement status

It does **not** perform:

- Anomaly detection
- Path comparison
- Root-cause diagnosis
- Hypothesis generation
- Final recommendations

## Architecture

```text
Target
   |
   +------------------+
   |                  |
   v                  v
  DNS                HTTP
   |                  |
   +--------+---------+
            |
            v
       Traceroute
            |
            v
    Structured Evidence
            |
            v
        Person 2
```

## API

- `POST /investigate` -- Person 1 raw collection only (DNS, HTTP, TCP, TLS, traceroute), returned as-is.
- `POST /diagnose` -- the full pipeline: collect, compare against the previous run of the same target (Person 2), then run the Bayesian diagnosis engine (Person 3) and return one combined result shaped for the frontend. This is what the React app calls.

Both take `{"target": "<domain or IP>"}`.
