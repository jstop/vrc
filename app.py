"""
Verifiable Reasoning Credential (VRC) — Web Application

Paste text → Claude extracts claims & attack relations →
Dung solver computes extensions → visual map + downloadable VRC JSON.
"""

import json
import os
import hashlib
import datetime
import uuid
import re
from decimal import Decimal
from dotenv import load_dotenv
from flask import Flask, render_template, request, jsonify

load_dotenv(os.path.expanduser("~/.api_keys/env"))
from anthropic import Anthropic
from dung_solver import ArgumentationFramework, build_framework

app = Flask(__name__)

DYNAMODB_TABLE = os.environ.get("DYNAMODB_TABLE")

# ---------------------------------------------------------------------------
# DynamoDB backend (used when DYNAMODB_TABLE is set, i.e. on Lambda)
# ---------------------------------------------------------------------------
if DYNAMODB_TABLE:
    import boto3

    _ddb = boto3.resource("dynamodb")
    _table = _ddb.Table(DYNAMODB_TABLE)

    def _ddb_save(source_hash, source_text, summary_label, acc, rej, und, result_json, handle="anon", topic=""):
        ts = datetime.datetime.utcnow().isoformat() + "Z"
        sk = f"{ts}#{uuid.uuid4().hex[:8]}"
        _table.put_item(Item={
            "pk": "ANALYSIS",
            "sk": sk,
            "source_hash": source_hash,
            "source_text": source_text,
            "summary_label": summary_label,
            "topic": topic,
            "accepted": acc,
            "rejected": rej,
            "undecided": und,
            "result_json": result_json,
            "handle": handle,
            "gsi1pk": "FEED",
            "gsi1sk": sk,
        })
        return sk

    def _ddb_list():
        resp = _table.query(
            KeyConditionExpression=boto3.dynamodb.conditions.Key("pk").eq("ANALYSIS"),
            ScanIndexForward=False,
            Limit=50,
            ProjectionExpression="sk, summary_label, topic, accepted, rejected, undecided, source_hash, handle",
        )
        rows = []
        for item in resp.get("Items", []):
            rows.append({
                "id": item["sk"],
                "created_at": item["sk"].split("#")[0],
                "summary_label": item["summary_label"],
                "topic": item.get("topic", ""),
                "accepted": int(item["accepted"]),
                "rejected": int(item["rejected"]),
                "undecided": int(item["undecided"]),
                "source_hash": item["source_hash"],
                "handle": item.get("handle", "anon"),
            })
        return rows

    def _ddb_feed(cursor=None, limit=20):
        kwargs = {
            "IndexName": "gsi1",
            "KeyConditionExpression": boto3.dynamodb.conditions.Key("gsi1pk").eq("FEED"),
            "ScanIndexForward": False,
            "Limit": limit,
            "ProjectionExpression": "sk, summary_label, topic, accepted, rejected, undecided, source_hash, handle",
        }
        if cursor:
            kwargs["ExclusiveStartKey"] = json.loads(cursor)
        resp = _table.query(**kwargs)
        rows = []
        for item in resp.get("Items", []):
            rows.append({
                "id": item["sk"],
                "created_at": item["sk"].split("#")[0],
                "summary_label": item["summary_label"],
                "topic": item.get("topic", ""),
                "accepted": int(item["accepted"]),
                "rejected": int(item["rejected"]),
                "undecided": int(item["undecided"]),
                "source_hash": item["source_hash"],
                "handle": item.get("handle", "anon"),
            })
        next_cursor = None
        if "LastEvaluatedKey" in resp:
            next_cursor = json.dumps(resp["LastEvaluatedKey"], default=str)
        return rows, next_cursor

    def _ddb_get(sk):
        resp = _table.get_item(Key={"pk": "ANALYSIS", "sk": sk})
        item = resp.get("Item")
        if not item:
            return None
        result = json.loads(item["result_json"])
        result["source_text"] = item["source_text"]
        result["handle"] = item.get("handle", "anon")
        return result

    def _ddb_delete(sk):
        _table.delete_item(Key={"pk": "ANALYSIS", "sk": sk})

# ---------------------------------------------------------------------------
# SQLite backend (local dev)
# ---------------------------------------------------------------------------
else:
    import sqlite3

    DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "vrc.db")

    def _init_db():
        conn = sqlite3.connect(DB_PATH)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS analyses (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at    TEXT    NOT NULL DEFAULT (datetime('now')),
                source_hash   TEXT    NOT NULL,
                source_text   TEXT    NOT NULL,
                summary_label TEXT    NOT NULL DEFAULT '',
                accepted      INTEGER NOT NULL DEFAULT 0,
                rejected      INTEGER NOT NULL DEFAULT 0,
                undecided     INTEGER NOT NULL DEFAULT 0,
                result_json   TEXT    NOT NULL
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_created ON analyses(created_at DESC)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_source_hash ON analyses(source_hash)")
        # Add handle column if missing (migration for existing DBs)
        try:
            conn.execute("ALTER TABLE analyses ADD COLUMN handle TEXT NOT NULL DEFAULT 'anon'")
        except sqlite3.OperationalError:
            pass  # column already exists
        # Add topic column if missing
        try:
            conn.execute("ALTER TABLE analyses ADD COLUMN topic TEXT NOT NULL DEFAULT ''")
        except sqlite3.OperationalError:
            pass  # column already exists
        conn.commit()
        conn.close()

    def _get_db():
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        return conn

    _init_db()

    def _ddb_feed(cursor=None, limit=20):
        db = _get_db()
        offset = int(cursor) if cursor else 0
        rows = db.execute(
            """SELECT id, created_at, summary_label, topic, accepted, rejected, undecided, source_hash, handle
               FROM analyses ORDER BY created_at DESC LIMIT ? OFFSET ?""",
            (limit, offset),
        ).fetchall()
        db.close()
        items = [dict(r) for r in rows]
        next_cursor = str(offset + limit) if len(items) == limit else None
        return items, next_cursor

client = Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY", ""))

EXTRACTION_PROMPT = """You are a formal argumentation analyst. Given the following text, extract:

1. The discrete CLAIMS made (factual assertions, conclusions, premises, recommendations). 
   Each claim should be a single, self-contained proposition.
   Give each an ID like c1, c2, c3...

2. The ATTACK relations between claims. Claim A attacks claim B if:
   - A directly contradicts B
   - A undermines a premise that B depends on
   - A provides evidence against B's conclusion
   - Accepting A gives reason to reject B

3. The SUPPORT relations between claims (for display, not used in Dung computation).
   Claim A supports claim B if A provides evidence or reasoning for B.

IMPORTANT RULES:
- Extract 3-15 claims. Too few and the analysis is trivial. Too many and it's noise.
- Only include attacks where there's genuine logical tension, not just difference in topic.
- Each claim must be a clear proposition, not a question or vague statement.
- Be precise about what attacks what. Direction matters.
- If two claims directly contradict each other (accepting either gives reason to reject the other), include attacks in BOTH directions. Mutual attacks are expected when claims are genuine opposites.

Respond with ONLY valid JSON in this exact format, no other text:

{
  "topic": "A short (3-8 word) title describing the subject matter of the text",
  "claims": [
    {"id": "c1", "text": "The specific claim text"},
    {"id": "c2", "text": "Another claim"}
  ],
  "attacks": [
    {"from": "c1", "to": "c2", "reason": "Brief explanation of why c1 undermines c2"}
  ],
  "supports": [
    {"from": "c1", "to": "c3", "reason": "Brief explanation of support relation"}
  ]
}"""


def extract_claims(text: str) -> dict:
    """Use Claude to extract claims and relations from text."""
    message = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=4000,
        messages=[
            {
                "role": "user",
                "content": f"{EXTRACTION_PROMPT}\n\n---\n\nTEXT TO ANALYZE:\n\n{text}",
            }
        ],
    )

    response_text = message.content[0].text.strip()
    # Strip markdown code fences if present
    if response_text.startswith("```"):
        response_text = response_text.split("\n", 1)[1]
    if response_text.endswith("```"):
        response_text = response_text.rsplit("```", 1)[0]
    response_text = response_text.strip()

    return json.loads(response_text)


def build_vrc(text: str, extraction: dict, analysis: dict) -> dict:
    """Build a Verifiable Reasoning Credential from the analysis."""
    # Create a content hash for integrity
    content = json.dumps(
        {"text": text, "extraction": extraction, "analysis": analysis},
        sort_keys=True,
    )
    content_hash = hashlib.sha256(content.encode()).hexdigest()

    return {
        "@context": [
            "https://www.w3.org/2018/credentials/v1",
            "https://vrc.example/v1",
        ],
        "type": ["VerifiableCredential", "VerifiableReasoningCredential"],
        "issuanceDate": datetime.datetime.utcnow().isoformat() + "Z",
        "credentialSubject": {
            "type": "ReasoningAnalysis",
            "sourceTextHash": hashlib.sha256(text.encode()).hexdigest(),
            "argumentationFramework": {
                "arguments": extraction["claims"],
                "attacks": extraction["attacks"],
                "supports": extraction.get("supports", []),
            },
            "extensions": {
                "grounded": analysis["grounded_extension"],
                "preferred": analysis["preferred_extensions"],
                "stable": analysis["stable_extensions"],
            },
            "argumentStatus": analysis["argument_status"],
            "summary": analysis["summary"],
        },
        "proof": {
            "type": "ContentIntegrityHash",
            "created": datetime.datetime.utcnow().isoformat() + "Z",
            "contentHash": content_hash,
            "note": "This prototype uses content hashing. Production would use cryptographic signatures.",
        },
    }


HANDLE_RE = re.compile(r'^[a-zA-Z0-9_-]{2,24}$')


def _sanitize_handle(raw):
    """Validate and return a handle, or 'anon' if invalid."""
    if not raw or not isinstance(raw, str):
        return "anon"
    raw = raw.strip().lstrip("@")
    if HANDLE_RE.match(raw):
        return raw
    return "anon"


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/analyze", methods=["POST"])
def analyze():
    data = request.get_json()
    text = data.get("text", "").strip()
    handle = _sanitize_handle(data.get("handle"))

    if not text:
        return jsonify({"error": "No text provided"}), 400

    if len(text) > 15000:
        return jsonify({"error": "Text too long. Please keep under 15,000 characters."}), 400

    try:
        # Step 1: Extract claims and relations via Claude
        extraction = extract_claims(text)

        # Step 2: Build argumentation framework and compute extensions
        af = build_framework(extraction["claims"], extraction["attacks"])
        analysis = af.full_analysis()

        # Step 3: Build the VRC
        vrc = build_vrc(text, extraction, analysis)

        result = {
            "claims": extraction["claims"],
            "attacks": extraction["attacks"],
            "supports": extraction.get("supports", []),
            "analysis": analysis,
            "vrc": vrc,
        }

        # Step 4: Persist
        topic = extraction.get("topic", "")
        summary = analysis.get("summary", {})
        acc = summary.get("accepted", 0)
        rej = summary.get("rejected", 0)
        und = summary.get("undecided", 0)
        total = acc + rej + und
        if rej == 0 and und == 0:
            summary_label = f"{total} claims · all accepted"
        elif und == 0:
            summary_label = f"{total} claims · {acc} accepted, {rej} rejected"
        else:
            summary_label = f"{total} claims · {acc} accepted, {rej} rejected, {und} undecided"
        source_hash = hashlib.sha256(text.encode()).hexdigest()

        if DYNAMODB_TABLE:
            row_id = _ddb_save(source_hash, text, summary_label, acc, rej, und, json.dumps(result), handle, topic)
        else:
            db = _get_db()
            cur = db.execute(
                """INSERT INTO analyses
                   (source_hash, source_text, summary_label, topic, accepted, rejected, undecided, result_json, handle)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (source_hash, text, summary_label, topic, acc, rej, und, json.dumps(result), handle),
            )
            db.commit()
            row_id = cur.lastrowid
            db.close()

        result["id"] = row_id
        result["handle"] = handle
        return jsonify(result)

    except json.JSONDecodeError as e:
        return jsonify({"error": f"Failed to parse claim extraction: {str(e)}"}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/feed")
def feed():
    """Public paginated feed of all analyses, newest first."""
    cursor = request.args.get("cursor")
    limit = min(int(request.args.get("limit", 20)), 50)
    items, next_cursor = _ddb_feed(cursor, limit)
    result = {"items": items}
    if next_cursor:
        result["next_cursor"] = next_cursor
    return jsonify(result)


@app.route("/history")
def history():
    """Return last 50 analyses (lightweight — no full text or result blob)."""
    if DYNAMODB_TABLE:
        return jsonify(_ddb_list())
    db = _get_db()
    rows = db.execute(
        """SELECT id, created_at, summary_label, topic, accepted, rejected, undecided, source_hash, handle
           FROM analyses ORDER BY created_at DESC LIMIT 50"""
    ).fetchall()
    db.close()
    return jsonify([dict(r) for r in rows])


@app.route("/analysis/<path:analysis_id>")
def get_analysis(analysis_id):
    """Return full result_json + source_text + handle for a saved analysis."""
    if DYNAMODB_TABLE:
        result = _ddb_get(analysis_id)
        if not result:
            return jsonify({"error": "Analysis not found"}), 404
        return jsonify(result)
    db = _get_db()
    row = db.execute(
        "SELECT result_json, source_text, handle FROM analyses WHERE id = ?", (int(analysis_id),)
    ).fetchone()
    db.close()
    if not row:
        return jsonify({"error": "Analysis not found"}), 404
    result = json.loads(row["result_json"])
    result["source_text"] = row["source_text"]
    result["handle"] = row["handle"] if row["handle"] else "anon"
    return jsonify(result)


@app.route("/analysis/<path:analysis_id>", methods=["DELETE"])
def delete_analysis(analysis_id):
    """Delete a single saved analysis."""
    if DYNAMODB_TABLE:
        _ddb_delete(analysis_id)
        return jsonify({"ok": True})
    db = _get_db()
    db.execute("DELETE FROM analyses WHERE id = ?", (int(analysis_id),))
    db.commit()
    db.close()
    return jsonify({"ok": True})


@app.route("/health")
def health():
    return jsonify({"status": "ok", "service": "vrc"})


# ---------------------------------------------------------------------------
# Lambda entry-point (ignored when running locally)
# ---------------------------------------------------------------------------
try:
    from mangum import Mangum
    from asgiref.wsgi import WsgiToAsgi
    handler = Mangum(WsgiToAsgi(app))
except ImportError:
    pass

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port, debug=False)
