# STATIC E11 TEMPLATE ONLY. DO NOT BUILD BEFORE A DISTINCT R3-E12 RUNTIME-OVERLAY AUTHORIZATION.
ARG BASE_IMAGE
FROM ${BASE_IMAGE}
COPY r3_e11_xmla_measurement_app.py /app/r3_e11_xmla_measurement_app.py
COPY datawarehouses.r3e.yaml /app/datawarehouses.yaml
ENV MCAD_DW_REGISTRY=/app/datawarehouses.yaml
CMD ["uvicorn", "r3_e11_xmla_measurement_app:app", "--host", "0.0.0.0", "--port", "9000", "--log-level", "info", "--access-log"]
