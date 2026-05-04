FROM eclipse-temurin:17-jre

RUN apt-get update \
 && apt-get install -y --no-install-recommends python3 python3-pip python3-venv curl \
 && rm -rf /var/lib/apt/lists/*

ENV VIRTUAL_ENV=/opt/venv
RUN python3 -m venv "$VIRTUAL_ENV"
ENV PATH="$VIRTUAL_ENV/bin:$PATH"

RUN pip install --no-cache-dir \
    opendataloader-pdf \
    fastapi \
    "uvicorn[standard]" \
    python-multipart

WORKDIR /app
COPY app.py .

EXPOSE 9385

HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
  CMD curl -fsS http://localhost:9385/health || exit 1

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "9385"]
