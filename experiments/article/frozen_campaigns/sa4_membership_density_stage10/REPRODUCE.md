# Verification and independent reproduction

## Verify the frozen package

```bash
cd experiments/article/frozen_campaigns/sa4_membership_density_stage10
sha256sum -c SHA256SUMS
sha256sum -c archive/membership_density_stage10_canonical_20260804T161119Z.tar.gz.sha256 --ignore-missing
```

## Verify the canonical payload

```bash
mkdir -p /tmp/membership-density-stage10
tar -xzf archive/membership_density_stage10_canonical_20260804T161119Z.tar.gz -C /tmp/membership-density-stage10
cd /tmp/membership-density-stage10
sha256sum -c PAYLOAD_SHA256SUMS
```

## Independent analyzer reproduction

The canonical repository execution count remains exactly one. Independent reproduction must write outside the canonical repository output paths.

```bash
cd /tmp/membership-density-stage10/payload
python backend/harness/sensitivity_execution/analyze_clustered_timing_precision_v2.py \
  --stage-size \
  10 \
  --observations \
  reports/article_experiments/sensitivity/e3_controlled_execution/audits/membership_density/timing_stage10/precision_analysis/stage10_portfolio_measurement_observations.csv \
  --timing-report \
  reports/article_experiments/sensitivity/e3_controlled_execution/audits/membership_density/timing_stage10/precision_analysis/analyzer_timing_report_adapter.json \
  --intervals-csv \
  reports/article_experiments/sensitivity/e3_controlled_execution/audits/membership_density/timing_stage10/precision_analysis/raw_analyzer_intervals.csv \
  --report-json \
  reports/article_experiments/sensitivity/e3_controlled_execution/audits/membership_density/timing_stage10/precision_analysis/raw_analyzer_report.json \
  --report-md \
  reports/article_experiments/sensitivity/e3_controlled_execution/audits/membership_density/timing_stage10/precision_analysis/raw_analyzer_report.md \
  --levels \
  25,50,75,100 \
  --steps \
  0 \
  --measurements-per-cluster \
  2300 \
  --bootstrap-repetitions \
  10000 \
  --bootstrap-seed \
  20260728 \
  --confidence-level \
  0.95 \
  --median-target \
  0.10 \
  --p95-target \
  0.15
```
