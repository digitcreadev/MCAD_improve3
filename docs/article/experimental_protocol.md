# Experimental protocol

The experimental evaluation is organized into three complementary campaigns.

The first campaign evaluates the core MCAD-Gate mechanism on FoodMart using 3000 controlled analytical sessions.

The second campaign assesses multi-dataset generalization over FoodMart, AdventureWorksDW and SteelWheels using 1200 sessions.

The third campaign evaluates backend portability over SQL Direct and XMLA/eMondrian execution paths using 480 validation runs.

Overall, the evaluation covers 4680 sessions or validation runs and 37440 query-level decisions.

In the core and multi-dataset campaigns, policy comparisons are performed on paired analytical traces, ensuring that MCAD-Gate and the baselines are evaluated under the same objectives, datasets, session lengths and query sequences.

The generated artifacts are stored under timestamped run directories. UTC timestamps are used as the canonical time reference for reproducibility.
