# V9.4.2a — Restore FoodMart XMLA/eMondrian Stack

## Goal

This patch restores the XMLA/eMondrian path in the current `bi-stack/docker-compose.yml`.
The current proxy already exposes `/xmla` and still points by default to:

```text
http://emondrian:8080/emondrian/xmla
```

but the active Docker Compose stack only declared `mcad-api` and `mcad-proxy`. Therefore the XMLA route existed in code but had no real upstream service in the Docker network.

## Restored services

The patch adds:

```text
emondrian  -> real XMLA/Mondrian OLAP engine for FoodMart MDX
pivot4j    -> optional OLAP UI client that connects through mcad-proxy /xmla
```

The service list must become:

```text
emondrian
pivot4j
mcad-api
mcad-proxy
```

## Execution contract

The XMLA path must always remain MCAD-gated:

```text
MDX request
  -> mcad-proxy /xmla
  -> mcad-api /eval
  -> BLOCK: return XMLA fault / no upstream call
  -> ALLOW: forward to eMondrian / XMLA
  -> result is summarized and CKG is updated
```

No XMLA request should be forwarded to eMondrian before MCAD `/eval` returns `ALLOW`.

## Ports

```text
mcad-api   : http://127.0.0.1:8000
mcad-proxy : http://127.0.0.1:9000
emondrian  : http://127.0.0.1:8081/emondrian/xmla
pivot4j    : http://127.0.0.1:8090/pivot4j
```

## Apply

```bash
cp /mnt/data/mcad_v9_4_2a_restore_foodmart_xmla_stack_tree/bi-stack/docker-compose.yml \
   bi-stack/docker-compose.yml

mkdir -p bi-stack/docs bi-stack/scripts
cp /mnt/data/mcad_v9_4_2a_restore_foodmart_xmla_stack_tree/bi-stack/docs/V9_4_2A_RESTORE_FOODMART_XMLA_STACK.md \
   bi-stack/docs/V9_4_2A_RESTORE_FOODMART_XMLA_STACK.md
cp /mnt/data/mcad_v9_4_2a_restore_foodmart_xmla_stack_tree/bi-stack/scripts/check_foodmart_xmla_regression.sh \
   bi-stack/scripts/check_foodmart_xmla_regression.sh
chmod +x bi-stack/scripts/check_foodmart_xmla_regression.sh
```

## Verify static configuration

```bash
docker compose -f bi-stack/docker-compose.yml config --services
bash bi-stack/scripts/check_foodmart_xmla_regression.sh . static
```

Expected services:

```text
emondrian
pivot4j
mcad-api
mcad-proxy
```

## Rebuild and run

```bash
docker compose -f bi-stack/docker-compose.yml build --no-cache emondrian pivot4j mcad-proxy
docker compose -f bi-stack/docker-compose.yml up -d
```

## Verify live XMLA path

```bash
bash bi-stack/scripts/check_foodmart_xmla_regression.sh . live
```

If live checks fail, inspect:

```bash
docker compose -f bi-stack/docker-compose.yml logs -f emondrian mcad-proxy pivot4j
```

## Scope

This patch does not modify:

```text
backend/mcad/engine.py
experiments/article/*
backend/ckg/ckg_updater.py
scripts/reproduce_article_artifacts.sh
```

It restores the real XMLA infrastructure only.
