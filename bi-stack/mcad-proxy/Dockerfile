FROM python:3.11-slim

WORKDIR /app
RUN pip install --no-cache-dir fastapi uvicorn requests lxml pyyaml python-tds
RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*

COPY app.py /app/app.py
COPY xmla_result_parser.py /app/xmla_result_parser.py
COPY direct_executor.py /app/direct_executor.py
COPY direct_result_materializer.py /app/direct_result_materializer.py
COPY datawarehouses.yaml /app/datawarehouses.yaml
COPY execution /app/execution
COPY session_ui.html /app/session_ui.html  
COPY static /app/static

ENV UPSTREAM_XMLA=http://emondrian:8080/emondrian/xmla
ENV MCAD_EVAL_URL=http://mcad-api:8000/eval
ENV MCAD_CKG_URL=http://mcad-api:8000/ckg/update
ENV MCAD_API_BASE=http://mcad-api:8000
ENV MCAD_BI_MODE=hybrid
ENV MCAD_DW_REGISTRY=/app/datawarehouses.yaml
ENV MCAD_DEMO_EVIDENCE_DIR=/app/demo-evidence

EXPOSE 9000
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "9000"]
