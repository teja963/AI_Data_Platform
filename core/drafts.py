import json
from pathlib import Path

DRAFTS_FILE = Path(__file__).resolve().parents[1] / "data" / "editor_drafts.json"


def _read_drafts():
    if not DRAFTS_FILE.exists():
        return {}

    try:
        data = json.loads(DRAFTS_FILE.read_text())
    except (json.JSONDecodeError, OSError):
        return {}

    drafts = data.get("drafts", {})
    return drafts if isinstance(drafts, dict) else {}


def _write_drafts(drafts):
    DRAFTS_FILE.parent.mkdir(parents=True, exist_ok=True)
    DRAFTS_FILE.write_text(json.dumps({"drafts": drafts}, indent=2, sort_keys=True))


def load_draft(draft_key, default=""):
    drafts = _read_drafts()
    return drafts.get(draft_key, default)


def save_draft(draft_key, content):
    drafts = _read_drafts()
    drafts[draft_key] = content
    _write_drafts(drafts)


def delete_draft(draft_key):
    drafts = _read_drafts()
    if draft_key in drafts:
        drafts.pop(draft_key, None)
        _write_drafts(drafts)
