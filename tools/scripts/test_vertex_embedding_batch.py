"""Empirically test whether Gemini's gemini-embedding-* models accept
multiple inputs in a single embed_content call.

Configuration is loaded from docker/.env at the repo root (override with
DOTENV_PATH=/some/other/.env). Variables already exported in the shell take
precedence over docker/.env entries.

Add ONE of the following blocks to docker/.env:

  # 1) Gemini API key (simplest)
  GOOGLE_API_KEY=your_gemini_api_key
  # optional: route through Vertex AI Express mode (api-key auth on Vertex)
  # GOOGLE_USE_VERTEX=1

  # 2) Service account JSON on disk (Vertex AI standard auth)
  GOOGLE_APPLICATION_CREDENTIALS=/abs/path/to/service-account.json
  GOOGLE_PROJECT_ID=your-project
  GOOGLE_REGION=us-central1

Optional in either mode:

  GOOGLE_EMBED_MODEL=gemini-embedding-001    # default

Run:

    uv run python tools/scripts/test_vertex_embedding_batch.py

The script issues embed_content requests with batch sizes 1, 2, 5, 16 and
reports the response shape (or the API error) for each, so you can see
empirically whether multi-input requests are accepted.
"""

from __future__ import annotations

import os
import sys
import traceback
from pathlib import Path


def load_dotenv(path: Path) -> int:
    """Minimal .env loader: KEY=VALUE per line, # comments, optional quotes.
    Existing os.environ values win. Returns the number of vars loaded."""
    if not path.is_file():
        return 0
    loaded = 0
    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export "):].lstrip()
        if "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip()
        if not key:
            continue
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
            value = value[1:-1]
        if key in os.environ:
            continue
        os.environ[key] = value
        loaded += 1
    return loaded


def _truthy(val: str | None) -> bool:
    return (val or "").strip().lower() in {"1", "true", "yes", "on"}


def make_client():
    from google import genai

    api_key = os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY")
    cred_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
    project_id = os.environ.get("GOOGLE_PROJECT_ID")
    region = os.environ.get("GOOGLE_REGION")
    use_vertex = _truthy(os.environ.get("GOOGLE_USE_VERTEX"))

    if api_key:
        if use_vertex:
            # Vertex AI Express mode: api key alone — project/location are
            # encoded in the key itself and are mutually exclusive with it
            # in the genai SDK initializer.
            client = genai.Client(vertexai=True, api_key=api_key)
            return client, "Vertex AI (api key, Express mode)"
        client = genai.Client(api_key=api_key)
        return client, "Gemini API (api key)"

    if cred_path:
        from google.oauth2 import service_account

        if not project_id or not region:
            raise SystemExit("Service-account auth requires GOOGLE_PROJECT_ID and GOOGLE_REGION")
        scopes = ["https://www.googleapis.com/auth/cloud-platform"]
        credits = service_account.Credentials.from_service_account_file(cred_path, scopes=scopes)
        client = genai.Client(vertexai=True, project=project_id, location=region, credentials=credits)
        return client, f"Vertex AI (service account) project={project_id} region={region}"

    raise SystemExit(
        "No credentials found. Set GOOGLE_API_KEY (Gemini API) or GOOGLE_APPLICATION_CREDENTIALS "
        "(+ GOOGLE_PROJECT_ID / GOOGLE_REGION) for Vertex."
    )


def build_config(types_module, task_type_name: str = "RETRIEVAL_DOCUMENT"):
    task_type = task_type_name
    if hasattr(types_module, "TaskType"):
        task_type = getattr(types_module.TaskType, task_type_name, task_type_name)
    try:
        return types_module.EmbedContentConfig(task_type=task_type)
    except TypeError:
        return None


def parse_embeddings(response):
    embeddings = getattr(response, "embeddings", None)
    if embeddings is None and isinstance(response, dict):
        embeddings = response.get("embeddings")
    return list(embeddings or [])


def probe(client, types_module, model_name: str, batch_size: int):
    inputs = [f"Gemini embedding batch probe sample number {i}." for i in range(batch_size)]
    config = build_config(types_module)
    print(f"\n=== batch_size={batch_size} model={model_name} ===")
    try:
        kwargs = {"model": model_name, "contents": inputs}
        if config is not None:
            kwargs["config"] = config
        result = client.models.embed_content(**kwargs)
        embeddings = parse_embeddings(result)
        print(f"OK    -> inputs={len(inputs)} embeddings_returned={len(embeddings)}")
        if embeddings:
            first = embeddings[0]
            values = getattr(first, "values", None)
            if values is None and isinstance(first, dict):
                values = first.get("values") or first.get("embedding")
            dim = len(values) if values is not None else "?"
            print(f"      first embedding dim={dim}")
    except Exception as exc:
        print(f"ERROR -> {type(exc).__name__}: {exc}")
        traceback.print_exc(limit=2)


def main() -> int:
    repo_root = Path(__file__).resolve().parents[2]
    dotenv_path = Path(os.environ.get("DOTENV_PATH") or (repo_root / "docker" / ".env"))
    loaded = load_dotenv(dotenv_path)
    print(f"dotenv: {dotenv_path} ({'loaded ' + str(loaded) + ' vars' if loaded else 'not loaded'})")

    model_name = os.environ.get("GOOGLE_EMBED_MODEL", "gemini-embedding-001")

    from google.genai import types

    client, label = make_client()
    print(f"Embedding probe: {label} model={model_name}")

    for batch_size in (1, 2, 5, 16):
        probe(client, types, model_name, batch_size)

    return 0


if __name__ == "__main__":
    sys.exit(main())
