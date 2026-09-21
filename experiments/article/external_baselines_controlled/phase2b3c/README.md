# Phase 2B-3C1: controlled native Delian smoke contract

This directory is a **contract freeze only**. It contains declarative plans,
schemas, provenance, native assertion oracles, and static/unit tests for a
future Phase 2B-3C2 run. It contains no runner and authorizes no execution of
Maven, Java tests, Delian, MySQL, Docker, databases, network requests,
subprocesses, benchmarks, Djedaini, ASSESS, or historical MCAD campaigns.

Validate this frozen contract without executing the future smoke:

```text
python validate_plan.py
python -m pytest -q tests
```

The first command only reads local JSON and performs schema-subset checks.
See `PREREGISTRATION.md` for the scientific interpretation boundary.
