import json
import os
import subprocess
import tempfile
from pathlib import Path

from fastapi import FastAPI, File, Form, Header, HTTPException, UploadFile

API_KEY = os.environ.get("API_KEY", "")

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
            "--input", str(in_pdf),
            "--output", str(out_dir),
            "--save-json",
            "--save-markdown",
        ]
        if hybrid:
            cmd += ["--hybrid", hybrid]
        if image_output:
            cmd += ["--image-output", image_output]
        if sanitize and sanitize.lower() == "true":
            cmd += ["--sanitize"]

        proc = subprocess.run(cmd, capture_output=True, text=True)
        if proc.returncode != 0:
            raise HTTPException(
                status_code=500,
                detail=f"opendataloader-pdf failed: {proc.stderr[:2000]}",
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
