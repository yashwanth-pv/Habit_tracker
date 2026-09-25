"""
github_storage.py
------------------
Treats a JSON file inside a GitHub repo as the "database" for the System.
Uses the GitHub Contents API (no external DB, no server — just your repo).

Required Streamlit secrets (see .streamlit/secrets.toml.example):
    GITHUB_TOKEN  -> a fine-grained Personal Access Token with
                     "Contents: Read and write" permission on the target repo
    GITHUB_REPO   -> "your-username/your-repo"
    GITHUB_PATH   -> path to the save file inside the repo, e.g. "data/save.json"
    GITHUB_BRANCH -> branch to read/write, e.g. "main"
"""

import base64
import json
import time

import requests
import streamlit as st

API_ROOT = "https://api.github.com"


def _headers():
    return {
        "Authorization": f"Bearer {st.secrets['GITHUB_TOKEN']}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def _url():
    repo = st.secrets["GITHUB_REPO"]
    path = st.secrets["GITHUB_PATH"]
    return f"{API_ROOT}/repos/{repo}/contents/{path}"


def _branch():
    return st.secrets.get("GITHUB_BRANCH", "main")


def load_state(default_state: dict) -> dict:
    """Fetch the save file from GitHub. Creates it with default_state if missing."""
    resp = requests.get(_url(), headers=_headers(), params={"ref": _branch()}, timeout=15)

    if resp.status_code == 200:
        payload = resp.json()
        content = base64.b64decode(payload["content"]).decode("utf-8")
        state = json.loads(content)
        state["_sha"] = payload["sha"]
        return state

    if resp.status_code == 404:
        # First run: create the save file in the repo.
        state = dict(default_state)
        sha = save_state(state, message="System: initialize hunter save file")
        state["_sha"] = sha
        return state

    raise RuntimeError(
        f"GitHub API error while loading save file ({resp.status_code}): {resp.text}"
    )


def save_state(state: dict, message: str = "System: update save file") -> str:
    """Write state to the GitHub save file. Returns the new blob sha."""
    body = dict(state)
    sha = body.pop("_sha", None)
    body.pop("_dirty", None)

    content_str = json.dumps(body, indent=2, ensure_ascii=False)
    content_b64 = base64.b64encode(content_str.encode("utf-8")).decode("utf-8")

    payload = {
        "message": message,
        "content": content_b64,
        "branch": _branch(),
    }
    if sha:
        payload["sha"] = sha

    resp = requests.put(_url(), headers=_headers(), json=payload, timeout=15)

    if resp.status_code in (200, 201):
        return resp.json()["content"]["sha"]

    if resp.status_code == 409:
        # Someone/something else wrote to the file between our load and save.
        # Retry once against the latest sha.
        time.sleep(0.5)
        latest = requests.get(_url(), headers=_headers(), params={"ref": _branch()}, timeout=15)
        latest.raise_for_status()
        payload["sha"] = latest.json()["sha"]
        resp2 = requests.put(_url(), headers=_headers(), json=payload, timeout=15)
        if resp2.status_code in (200, 201):
            return resp2.json()["content"]["sha"]
        raise RuntimeError(f"GitHub save conflict retry failed: {resp2.status_code} {resp2.text}")

    raise RuntimeError(f"GitHub API error while saving ({resp.status_code}): {resp.text}")


def connection_ok() -> tuple[bool, str]:
    """Quick check that secrets are present and the repo/path is reachable."""
    required = ["GITHUB_TOKEN", "GITHUB_REPO", "GITHUB_PATH"]
    missing = [k for k in required if k not in st.secrets]
    if missing:
        return False, f"Missing secrets: {', '.join(missing)}"
    try:
        resp = requests.get(
            f"{API_ROOT}/repos/{st.secrets['GITHUB_REPO']}",
            headers=_headers(),
            timeout=10,
        )
        if resp.status_code == 200:
            return True, "Connected"
        if resp.status_code == 401:
            return False, "Bad token (401) — check GITHUB_TOKEN"
        if resp.status_code == 404:
            return False, "Repo not found (404) — check GITHUB_REPO and token access"
        return False, f"GitHub responded {resp.status_code}"
    except Exception as e:  # noqa: BLE001
        return False, str(e)
