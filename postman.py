"""Serve a ready-to-use Postman collection built from this app's OpenAPI schema.

In Postman: Import -> Link -> https://<your-host>/postman.json
Everything is pre-configured: base_url, Bearer auth on every request, and the
"Login" request saves the access_token automatically. No manual setup needed.
"""

import json
import re
import uuid
from datetime import date

from fastapi import APIRouter, Request

router = APIRouter(tags=["Health"])

# Runs after the Login request: stores the token in the collection variable.
LOGIN_SCRIPT = [
    "const data = pm.response.json();",
    "if (data.access_token) {",
    "    pm.collectionVariables.set('token', data.access_token);",
    "    console.log('Token saved. All requests are now authorized.');",
    "}",
]

# Runs after every request: a 401 means the token expired or you logged out.
COLLECTION_SCRIPT = [
    "if (pm.response.code === 401) {",
    "    console.warn('401 Unauthorized: run Auth -> Login again to refresh the token.');",
    "}",
]


def _base_url(request: Request) -> str:
    # Render terminates HTTPS at its proxy, so trust its forwarded headers.
    proto = request.headers.get("x-forwarded-proto", request.url.scheme)
    host = request.headers.get("x-forwarded-host", request.url.netloc)
    return f"{proto}://{host}"


def _resolve(schema: dict, spec: dict) -> dict:
    ref = schema.get("$ref")
    if ref:
        name = ref.split("/")[-1]
        return _resolve(spec["components"]["schemas"][name], spec)
    if "anyOf" in schema:  # Optional[X] -> X
        for option in schema["anyOf"]:
            if option.get("type") != "null":
                return _resolve(option, spec)
    if "allOf" in schema and len(schema["allOf"]) == 1:
        return _resolve(schema["allOf"][0], spec)
    return schema


def _example(schema: dict, spec: dict, name: str = "", depth: int = 0):
    """Build a sample value for a JSON schema, so request bodies come pre-filled."""
    schema = _resolve(schema, spec)
    if depth > 5:
        return None
    if "example" in schema:
        return schema["example"]
    if schema.get("examples"):
        return schema["examples"][0]
    if "default" in schema and schema["default"] is not None:
        return schema["default"]
    if "enum" in schema:
        return schema["enum"][0]

    kind = schema.get("type")
    fmt = schema.get("format", "")
    lname = name.lower()
    if kind == "object" or "properties" in schema:
        return {
            key: _example(sub, spec, key, depth + 1)
            for key, sub in schema.get("properties", {}).items()
        }
    if kind == "array":
        return [_example(schema.get("items", {}), spec, name, depth + 1)]
    if kind == "integer":
        return 1
    if kind == "number":
        return 1000.0
    if kind == "boolean":
        return True
    if fmt == "email" or "email" in lname:
        return "user@example.com"
    if "password" in lname:
        return "your-password"
    if fmt == "date-time":
        return f"{date.today().isoformat()}T09:00:00"
    if fmt == "date" or lname.endswith("date") or lname.startswith("date"):
        return date.today().isoformat()
    if fmt == "time" or lname.endswith("_time"):
        return "09:00:00"
    if "phone" in lname:
        return "9876543210"
    return f"sample {name}".strip() if name else "string"


def _build_item(path: str, method: str, op: dict, spec: dict) -> dict:
    params = op.get("parameters", [])
    path_vars = [p for p in params if p["in"] == "path"]
    query = [p for p in params if p["in"] == "query"]

    postman_path = re.sub(r"\{(\w+)\}", r":\1", path).strip("/")
    url = {
        "raw": "{{base_url}}/" + postman_path,
        "host": ["{{base_url}}"],
        "path": postman_path.split("/") if postman_path else [],
        "variable": [
            {"key": p["name"], "value": "1", "description": p.get("description", "")}
            for p in path_vars
        ],
        "query": [
            {
                "key": p["name"],
                "value": str(_example(p.get("schema", {}), spec, p["name"])),
                "disabled": True,  # optional filters: tick the box to use one
            }
            for p in query
        ],
    }
    if url["query"]:
        url["raw"] += "?" + "&".join(f"{q['key']}={q['value']}" for q in url["query"])

    request = {"method": method.upper(), "header": [], "url": url}

    body_schema = (
        op.get("requestBody", {}).get("content", {}).get("application/json", {}).get("schema")
    )
    if body_schema:
        request["header"].append({"key": "Content-Type", "value": "application/json"})
        request["body"] = {
            "mode": "raw",
            "raw": json.dumps(_example(body_schema, spec), indent=2),
            "options": {"raw": {"language": "json"}},
        }

    # Public endpoints (login, register, health...) send no token.
    if not op.get("security"):
        request["auth"] = {"type": "noauth"}

    item = {"name": op.get("summary") or f"{method.upper()} {path}", "request": request}

    if path == "/auth/login":
        item["name"] = "Login (run me first)"
        item["event"] = [{"listen": "test", "script": {"type": "text/javascript", "exec": LOGIN_SCRIPT}}]
    return item


def build_collection(spec: dict, base_url: str) -> dict:
    folders: dict[str, list] = {}
    for path, ops in spec["paths"].items():
        for method, op in ops.items():
            if method.lower() == "head":
                continue
            tag = (op.get("tags") or ["Other"])[0]
            folders.setdefault(tag, []).append(_build_item(path, method, op, spec))

    # Put Auth first so "Login" is the first thing you see.
    ordered = sorted(folders.items(), key=lambda kv: (kv[0].lower() != "auth", kv[0]))
    for _, items in ordered:
        items.sort(key=lambda i: not i["name"].startswith("Login"))

    return {
        "info": {
            "_postman_id": str(uuid.uuid5(uuid.NAMESPACE_URL, base_url)),
            "name": spec["info"].get("title", "API"),
            "description": (
                "1. Open Auth -> Login (run me first), put your email/password in Body, Send.\n"
                "2. The token is saved automatically. Every other request now works.\n"
                "3. Got 401? Token expired (24h) or you logged out: run Login again."
            ),
            "schema": "https://schema.getpostman.com/json/collection/v2.1.0/collection.json",
        },
        "auth": {"type": "bearer", "bearer": [{"key": "token", "value": "{{token}}", "type": "string"}]},
        "variable": [
            {"key": "base_url", "value": base_url, "type": "string"},
            {"key": "token", "value": "", "type": "string"},
        ],
        "event": [{"listen": "test", "script": {"type": "text/javascript", "exec": COLLECTION_SCRIPT}}],
        "item": [{"name": tag, "item": items} for tag, items in ordered],
    }


@router.get("/postman.json", summary="Download Postman collection")
def postman_collection(request: Request):
    """Import this URL in Postman (Import -> Link). Auth and token handling are pre-configured."""
    return build_collection(request.app.openapi(), _base_url(request))
