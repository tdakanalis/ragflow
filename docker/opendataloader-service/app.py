import json
import os
import subprocess
import tempfile
from pathlib import Path

from fastapi import FastAPI, File, Form, Header, HTTPException, UploadFile

API_KEY = os.environ.get("API_KEY", "")
DEFAULT_HYBRID = os.environ.get("OPENDATALOADER_HYBRID", "").strip()
DEFAULT_HYBRID_MODE = os.environ.get("OPENDATALOADER_HYBRID_MODE", "").strip()
DEFAULT_HYBRID_URL = os.environ.get("OPENDATALOADER_HYBRID_URL", "").strip()
DEFAULT_HYBRID_FALLBACK = os.environ.get("OPENDATALOADER_HYBRID_FALLBACK", "").strip().lower() in ("1", "true", "yes")

app = FastAPI(title="opendataloader-service")


def _check_auth(authorization: str | None) -> None:
    if not API_KEY:
        return
    if authorization != f"Bearer {API_KEY}":
        raise HTTPException(status_code=401, detail="unauthorized")


@app.get("/health")
def health(authorization: str | None = Header(default=None)):
    _check_auth(authorization)
    return {"status": "ok"}


@app.post("/file_parse")
async def file_parse(
    file: UploadFile = File(...),
    hybrid: str | None = Form(default=None),
    image_output: str | None = Form(default=None),
    sanitize: str | None = Form(default=None),
    authorization: str | None = Header(default=None),
):
    _check_auth(authorization)

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        in_pdf = tmp_path / (file.filename or "input.pdf")
        in_pdf.write_bytes(await file.read())

        out_dir = tmp_path / "out"
        out_dir.mkdir()

        cmd = [
            "opendataloader-pdf",
            "-o", str(out_dir),
            "-f", "json,markdown",
            str(in_pdf),
        ]
        eff_hybrid = hybrid or DEFAULT_HYBRID
        if eff_hybrid:
            cmd += ["--hybrid", eff_hybrid]
            if DEFAULT_HYBRID_MODE:
                cmd += ["--hybrid-mode", DEFAULT_HYBRID_MODE]
            if DEFAULT_HYBRID_URL:
                cmd += ["--hybrid-url", DEFAULT_HYBRID_URL]
            if DEFAULT_HYBRID_FALLBACK:
                cmd += ["--hybrid-fallback"]
        if image_output:
            cmd += ["--image-output", image_output]
        if sanitize and sanitize.lower() == "true":
            cmd += ["--sanitize"]

        proc = subprocess.run(cmd, capture_output=True, text=True)
        if proc.returncode != 0:
            import logging as _lg
            _lg.error("opendataloader-pdf failed (rc=%s)\nSTDOUT: %s\nSTDERR: %s",
                      proc.returncode, proc.stdout[-2000:], proc.stderr[-2000:])
            raise HTTPException(
                status_code=500,
                detail=f"opendataloader-pdf failed (rc={proc.returncode}): "
                       f"{(proc.stderr or proc.stdout)[-2000:]}",
            )

        json_doc = None
        for p in sorted(out_dir.rglob("*.json")):
            try:
                json_doc = json.loads(p.read_text(encoding="utf-8"))
                break
            except Exception:
                continue

        md_text = None
        for p in sorted(out_dir.rglob("*.md")):
            try:
                md_text = p.read_text(encoding="utf-8")
                break
            except Exception:
                continue

        return {"json_doc": json_doc, "md_text": md_text}
