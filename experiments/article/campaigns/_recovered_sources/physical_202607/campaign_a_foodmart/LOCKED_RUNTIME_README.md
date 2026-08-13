# Locked Campaign A — FoodMart 1000 sessions

This directory contains the locked final evidence snapshot for
Campaign A.

## Scientific unit

Campaign A is reported as one consolidated experimental block of
1000 FoodMart sessions.

The execution was technically partitioned into ten resumable runs of
100 sessions each. These partitions are operational checkpoints, not
ten independent scientific campaigns.

## Consolidated results

- Sessions: 1000
- Query decisions: 7960
- ALLOW: 2266
- BLOCK: 5694
- Physical executions for ALLOW: 2266
- Physical executions for BLOCK: 0
- Blocked before business execution: 5694
- Canonical gate contract violations: 0
- HTTP errors: 0
- Decision mismatches: 0
- Locked CKG events: 2266

## Provenance

Original run:

reports/article_experiments/
foodmart_campaign_a_1000_ckg_first_20260701T114014Z/

Original CKG event file:

ckg_snapshot/ckg_events_final.jsonl

The file was restored from the archived historical reports package and
renamed to ckg_events.jsonl for consistency with locked Campaign B.
