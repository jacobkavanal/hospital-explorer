"""Save a response body and the information needed to trace it."""

from datetime import datetime, timezone
import hashlib
import json


def save_response(response, *, raw_dir, source, dataset_id, parameters, scope):
    retrieved_at = datetime.now(timezone.utc)
    capture = raw_dir / retrieved_at.strftime("%Y%m%dT%H%M%S.%fZ")
    capture.mkdir(parents=True, exist_ok=False)
    body = response.content
    (capture / "response.json").write_bytes(body)
    manifest = {
        "source": source,
        "dataset_id": dataset_id,
        "url": response.url,
        "parameters": parameters,
        "retrieved_at": retrieved_at.isoformat(),
        "http_status": response.status_code,
        "sha256": hashlib.sha256(body).hexdigest(),
        "scope": scope,
    }
    (capture / "manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    return capture
