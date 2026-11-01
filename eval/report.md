# ManualMind evaluation report

- Embedding provider: fake / fake-hash-384
- LLM provider: fake / fake-llm
- Vector backend: numpy
- RETRIEVAL_MIN_SCORE: 0.1

## Totals

| Metric | Value |
| --- | --- |
| Questions | 17 |
| Status accuracy | 70.6% |
| Citation precision | 83.3% |
| Key-phrase hit rate | 41.7% |
| Average latency | 8.2 ms |
| Isolation violations | 0 |

## Per question

| Machine | Question | Expected | Actual | Status | Citations | Phrases | Cited |
| --- | --- | --- | --- | --- | --- | --- | --- |
| M-HP200 | What does E17 mean? | ANSWERED | ANSWERED | ok | ok | FAIL | HP-OPS-01 p2 |
| M-AC90 | What does E17 mean? | ANSWERED | ANSWERED | ok | ok | ok | AC-OM-01 p2 |
| M-HP200 | What is the normal operating pressure range? | ANSWERED | ANSWERED | ok | ok | ok | HP-OPS-01 p1 |
| M-AC90 | What is the normal operating pressure range? | ANSWERED | ANSWERED | ok | ok | FAIL | AC-OM-01 p1 |
| M-HP200 | How often is the filter checked? | ANSWERED | ANSWERED | ok | ok | FAIL | HP-MNT-01 p2 |
| M-AC90 | How often should the AF-10 filter indicator be checked, and when is the planned filter replacement due? | ANSWERED | ANSWERED | ok | FAIL | FAIL | AC-OM-01 p2 |
| M-HP200 | What triggers E17 and what should be inspected first? | ANSWERED | ANSWERED | ok | FAIL | FAIL | HP-OPS-01 p3 |
| M-HP200 | What does E31 mean? | ANSWERED | ANSWERED | ok | ok | FAIL | HP-OPS-01 p2 |
| M-AC90 | What does E31 mean? | ANSWERED | ANSWERED | ok | ok | FAIL | AC-OM-01 p2 |
| M-HP200 | Oil has been in service 12 months but only 1,400 hours. Is replacement due? | ANSWERED | ANSWERED | ok | ok | ok | HP-MNT-01 p2 |
| M-AC90 | What should be recorded before escalation? | ANSWERED | ANSWERED | ok | ok | ok | AC-OM-01 p3 |
| M-HP200 | Can the assistant approve return to service? | ANSWERED | ANSWERED | ok | ok | ok | HP-MNT-01 p3 |
| M-HP200 | When is the AF-10 filter replaced? | INSUFFICIENT_EVIDENCE | ANSWERED | FAIL | FAIL | ok | HP-MNT-01 p2 |
| M-AC90 | What is the H46 oil replacement interval? | INSUFFICIENT_EVIDENCE | ANSWERED | FAIL | FAIL | ok | AC-OM-01 p3 |
| M-HP200 | What is the pump replacement price? | INSUFFICIENT_EVIDENCE | ANSWERED | FAIL | FAIL | ok | HP-OPS-01 p3 |
| M-AC90 | What is the tightening torque for the motor mount? | INSUFFICIENT_EVIDENCE | ANSWERED | FAIL | FAIL | ok | AC-OM-01 p2 |
| M-HP200 | What is the capital of France? | INSUFFICIENT_EVIDENCE | ANSWERED | FAIL | FAIL | ok | HP-OPS-01 p1 |

## Items to look at

- M-HP200: What does E17 mean? (missing 110 bar)
- M-AC90: What is the normal operating pressure range? (missing 7.0, 8.0)
- M-HP200: How often is the filter checked? (missing 50)
- M-AC90: How often should the AF-10 filter indicator be checked, and when is the planned filter replacement due? (cited AC-OM-01 p2; missing 100, 600)
- M-HP200: What triggers E17 and what should be inspected first? (cited HP-OPS-01 p3; missing 110 bar, reservoir)
- M-HP200: What does E31 mean? (missing guard)
- M-AC90: What does E31 mean? (missing condensate)
- M-HP200: When is the AF-10 filter replaced? (status ANSWERED; cited HP-MNT-01 p2)
- M-AC90: What is the H46 oil replacement interval? (status ANSWERED; cited AC-OM-01 p3)
- M-HP200: What is the pump replacement price? (status ANSWERED; cited HP-OPS-01 p3)
- M-AC90: What is the tightening torque for the motor mount? (status ANSWERED; cited AC-OM-01 p2)
- M-HP200: What is the capital of France? (status ANSWERED; cited HP-OPS-01 p1)
