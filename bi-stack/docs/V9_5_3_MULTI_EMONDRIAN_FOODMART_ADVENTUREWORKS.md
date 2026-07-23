# V9.5.3 — Multi-eMondrian FoodMart / AdventureWorks

This change separates XMLA runtimes by dataset.

## Runtime mapping

- FoodMart XMLA:
  - service: `emondrian-foodmart`
  - URL: `http://emondrian-foodmart:8080/emondrian/xmla`
  - catalog: `FoodMart`

- AdventureWorks XMLA:
  - service: `emondrian-adventureworks`
  - URL: `http://emondrian-adventureworks:8080/emondrian/xmla`
  - catalog: `AdventureWorksDW`

## Motivation

A single eMondrian instance with multiple datasources caused unstable XMLA catalog resolution.
Separating eMondrian instances preserves both FoodMart and AdventureWorks real XMLA paths.
