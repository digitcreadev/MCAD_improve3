# Article experimental evaluation

This directory contains the experimental harness used for the evaluation reported in the article.

The evaluation is organized into three complementary campaigns:

1. FoodMart core evaluation: 3000 controlled analytical sessions.
2. Multi-dataset generalization: 1200 sessions over FoodMart, AdventureWorksDW and SteelWheels.
3. Backend portability validation: 480 validation runs over SQL Direct and XMLA/eMondrian paths.

Overall, the evaluation covers 4680 sessions or validation runs and 37440 query-level decisions.

Generated outputs are written under:

reports/article_experiments/<run_id>/

Each run directory contains a manifest, logs, checksums, reports, CSV files and paired statistical results. UTC timestamps are used as the canonical time reference.
