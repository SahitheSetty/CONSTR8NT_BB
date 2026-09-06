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
        