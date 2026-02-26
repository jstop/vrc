"""
Verifiable Reasoning Credential (VRC) — Web Application

Paste text → Claude extracts claims & attack relations →
Dung solver computes extensions → visual map + downloadable VRC JSON.
"""

import json
import os
import hashlib
import datetime
from dotenv import load_dotenv
from flask import Flask, render_template, request, jsonify

load_dotenv(os.path.expanduser("~/.api_keys/env"))
from anthropic import Anthropic
from dung_solver import ArgumentationFramework, build_framework

app = Flask(__name__)

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

Respond with ONLY valid JSON in this exact format, no other text:

{
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


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/analyze", methods=["POST"])
def analyze():
    data = request.get_json()
    text = data.get("text", "").strip()

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

        return jsonify(
            {
                "claims": extraction["claims"],
                "attacks": extraction["attacks"],
                "supports": extraction.get("supports", []),
                "analysis": analysis,
                "vrc": vrc,
            }
        )

    except json.JSONDecodeError as e:
        return jsonify({"error": f"Failed to parse claim extraction: {str(e)}"}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/health")
def health():
    return jsonify({"status": "ok", "service": "vrc"})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port, debug=False)
