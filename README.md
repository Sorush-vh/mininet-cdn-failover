# Mininet-Based CDN with Fault-Tolerant Edge Delivery

A Python-based Content Delivery Network (CDN) simulation built with Mininet and Open vSwitch. The project models an Origin server, a Controller, multiple Edge servers, and Clients, and explores edge selection, in-memory caching, health monitoring, failover, resumable downloads, and HTTP content compression.

This is an academic Computer Networks project developed in two phases.

## Architecture

```text
                   +-------------------+
                   |     Controller    |
                   | HTTP API + UDP     |
                   | heartbeat monitor |
                   +---------+---------+
                             |
                      OpenFlow / OVS
                             |
          +------------------+------------------+
          |                  |                  |
   +------+-------+   +------+-------+   +------+------+
   |  Edge Server |   |  Edge Server |   |    Origin   |
   | cache/proxy  |   | cache/proxy  |   | source data |
   +------+-------+   +------+-------+   +-------------+
          \                  /
           \                /
            +-------+------+
                    |
                +---+---+
                | Client|
                +-------+
```

## Components

- **`cdn_topology.py`** — defines and launches the Mininet topology, including Origin, Controller, Edge, and Client nodes, link parameters, and Open vSwitch bridging.
- **`controller.py`** — receives UDP heartbeats from Edge servers, tracks edge availability, and exposes an HTTP endpoint for edge selection and cache-purge requests.
- **`edge_server.py`** — serves HTTP requests, maintains an in-memory cache, fetches cache misses from Origin, and sends periodic heartbeats.
- **`origin_server.py`** — provides the source content and, in Phase 2, reference SHA-256 hashes for integrity checks.
- **`client.py`** — requests content through the Controller and Edge servers, measures response behaviour, and runs the test scenarios.

## Implemented Features

### Phase 1 — CDN fundamentals

- Mininet topology with Origin, Controller, Edge servers, and Clients.
- Open vSwitch bridging and configured link delay/bandwidth.
- UDP heartbeat monitoring for Edge-server health.
- HTTP-based edge selection.
- In-memory edge caching and cache-miss retrieval from Origin.
- Controller-triggered cache purge.
- Concurrent client requests and baseline performance scenarios.

### Phase 2 — Resilience and bandwidth efficiency

- **Session migration and resumable downloads:** clients retain download offsets and request fixed-size chunks (64 KiB).
- **Failover:** when an Edge server becomes unavailable or times out, the client obtains a healthy Edge from the Controller and resumes from the last successfully received offset.
- **Gzip content compression:** Edge servers inspect `Accept-Encoding` and compress supported text content.
- **Encoding-aware cache keys:** cache entries distinguish compressed and uncompressed representations.
- **Integrity validation:** SHA-256 hashes verify that the reconstructed download matches the Origin content.

## Demonstrated Results

The submitted project reports document the following test observations:

| Scenario | Reported result |
|---|---:|
| Phase 1 cache-hit response | 62.6 ms |
| Phase 2 failover/session migration | 593.7 ms |
| Test file size before Gzip | 535,000 bytes |
| Transferred bytes with Gzip | 1,883 bytes |
| Reported transfer-size reduction | 99.6% |
| Download integrity | SHA-256 matched Origin |

These are results from the documented test setup, not general performance guarantees. Re-run the scenarios in the published environment before treating them as reproducible benchmark results.

## Requirements

The topology requires a Linux environment with Mininet and Open vSwitch. Python dependencies and exact versions should be listed in `requirements.txt` after the project environment is cleaned and verified.

Typical system prerequisites:

- Linux
- Python 3
- Mininet
- Open vSwitch
- `curl` or an equivalent HTTP client for manual checks

## Suggested Repository Layout

```text
mininet-cdn-failover/
├── README.md
├── requirements.txt
├── src/
│   ├── cdn_topology.py
│   ├── controller.py
│   ├── edge_server.py
│   ├── origin_server.py
│   └── client.py
├── docs/
│   ├── architecture.md
│   ├── phase1.md
│   └── phase2.md
├── scripts/
│   ├── run_topology.sh
│   └── run_scenarios.sh
└── results/
    ├── benchmark-summary.md
    └── figures/
```

## Running

The exact launch commands depend on the final cleaned version of the topology and the Mininet environment. Add verified commands here after testing the repository from a fresh clone; do not rely on paths or dependencies from the original coursework directory.

## Scope and Limitations

This is a network-emulation and coursework prototype, not a production CDN. The results are limited to the simulated topology, workload, and failure scenarios described in the project documentation. The repository should document known limitations, concurrency assumptions, cache consistency behaviour, and the controller's failure model.

## Author

Seyed Ali (Sorush) Vakilzadeh Hatefi  
GitHub: https://github.com/Sorush-vh
