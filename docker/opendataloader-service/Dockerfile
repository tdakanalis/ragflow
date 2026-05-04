FROM eclipse-temurin:17-jre

RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      python3 python3-pip python3-venv \
      curl \
      libxcb1 libgl1 libglib2.0-0 libsm6 libxext6 libxrender1 \
 && rm -rf /var/lib/apt/lists/*

ENV VIRTUAL_ENV=/opt/venv
RUN python3 -m venv "$VIRTUAL_ENV"
ENV PATH="$VIRTUAL_ENV/bin:$PATH"

RUN pip install --no-cache-dir \
    "opendataloader-pdf[hybrid]" \
    fastapi \
    "uvicorn[standard]" \
    python-multipart

WORKDIR /app
COPY app.py start.sh ./
RUN chmod +x /app/start.sh

EXPOSE 9385

HEALTHCHECK --interval=30s --timeout=5s --retries=3 --start-period=180s \
  CMD curl -fsS http://localhost:9385/health || exit 1

CMD ["/app/start.sh"]
