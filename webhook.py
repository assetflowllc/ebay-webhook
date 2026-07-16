"""
eBay Marketplace Account Deletion Notification Endpoint
Required by eBay Developer Program for all Production keysets.
https://developer.ebay.com/marketplace-account-deletion

Also provides Auth'n'Auth token flow endpoints:
  GET /auth/session  -> GetSessionID, returns sign-in URL
  GET /auth/callback -> FetchToken after user signs in, displays token
  GET /auth/token    -> View stored token
"""

import hashlib
import json
import os
import requests
from xml.etree import ElementTree as ET
from flask import Flask, request, jsonify

app = Flask(__name__)

_DEFAULT_ENDPOINT = "https://ebay-webhook-75c6.onrender.com/ebay/marketplace-deletion"
_DEFAULT_TOKEN = "5bf2e15aab5625ad37a4cd8e4646971cbae66596a557ea1e7c095b3c8fae43f2"

# eBay API credentials (hardcoded for convenience - single-user private server)
EBAY_APP_ID = "Oleksand-undefine-PRD-7625861e4-44e64d91"
EBAY_DEV_ID = "49416522-1c90-4f39-bdce-1f86662f19d0"
EBAY_CERT_ID = "PRD-625861e4a624-0bf0-467f-bf73-4959"
EBAY_RU_NAME = "Oleksandr_Karma-Oleksand-undefi-gbjsj"
EBAY_API_URL = "https://api.ebay.com/ws/api.dll"

_store = {}


def _trading_api_headers(call_name):
    return {
        "X-EBAY-API-CALL-NAME": call_name,
        "X-EBAY-API-SITEID": "0",
        "X-EBAY-API-COMPATIBILITY-LEVEL": "967",
        "X-EBAY-API-APP-NAME": EBAY_APP_ID,
        "X-EBAY-API-DEV-NAME": EBAY_DEV_ID,
        "X-EBAY-API-CERT-NAME": EBAY_CERT_ID,
        "Content-Type": "text/xml;charset=utf-8",
    }


def _xml_text(root, tag, ns="urn:ebay:apis:eBLBaseComponents"):
    return root.findtext(f"{{{ns}}}{tag}")


@app.route("/ebay/marketplace-deletion", methods=["GET", "POST"])
def marketplace_deletion():
    verification_token = os.environ.get("EBAY_VERIFICATION_TOKEN", _DEFAULT_TOKEN)
    endpoint_url = os.environ.get("EBAY_ENDPOINT_URL", _DEFAULT_ENDPOINT) or _DEFAULT_ENDPOINT

    if request.method == "GET":
        challenge_code = request.args.get("challenge_code", "")
        if not challenge_code:
            return jsonify({"error": "missing challenge_code"}), 400
        hash_input = challenge_code + verification_token + endpoint_url
        challenge_response = hashlib.sha256(hash_input.encode("utf-8")).hexdigest()
        print(f"[eBay] challenge={challenge_code[:16]}... response={challenge_response[:16]}...")
        return jsonify({"challengeResponse": challenge_response})

    data = request.get_json(silent=True) or {}
    print(f"[eBay] Account deletion notification: {json.dumps(data)}")
    return "", 200


@app.route("/auth/session", methods=["GET"])
def auth_session():
    xml = f"""<?xml version="1.0" encoding="utf-8"?>
<GetSessionIDRequest xmlns="urn:ebay:apis:eBLBaseComponents">
  <RequesterCredentials><eBayAuthToken></eBayAuthToken></RequesterCredentials>
  <RuName>{EBAY_RU_NAME}</RuName>
</GetSessionIDRequest>"""
    try:
        resp = requests.post(EBAY_API_URL, data=xml.encode("utf-8"),
                             headers=_trading_api_headers("GetSessionID"), timeout=15)
        root = ET.fromstring(resp.text)
        ack = _xml_text(root, "Ack")
        if ack not in ("Success", "Warning"):
            errors = [e.text for e in root.findall(".//{urn:ebay:apis:eBLBaseComponents}ShortMessage")]
            return jsonify({"error": "GetSessionID failed", "details": errors, "raw": resp.text}), 500
        session_id = _xml_text(root, "SessionID")
        if not session_id:
            return jsonify({"error": "No SessionID in response", "raw": resp.text}), 500
        _store["session_id"] = session_id
        sign_in_url = f"https://signin.ebay.com/ws/eBayISAPI.dll?SignIn&runame={EBAY_RU_NAME}&SessID={session_id}"
        return jsonify({"session_id": session_id, "sign_in_url": sign_in_url,
                        "instructions": "1. Open sign_in_url and sign in as assetflowco. 2. Click Agree and Continue. 3. Visit /auth/callback."})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/auth/callback", methods=["GET"])
def auth_callback():
    session_id = _store.get("session_id") or request.args.get("SessionID") or request.args.get("session_id")
    if not session_id:
        return jsonify({"error": "No session_id. Visit /auth/session first.", "args": dict(request.args)}), 400
    xml = f"""<?xml version="1.0" encoding="utf-8"?>
<FetchTokenRequest xmlns="urn:ebay:apis:eBLBaseComponents">
  <RequesterCredentials><eBayAuthToken></eBayAuthToken></RequesterCredentials>
  <SessionID>{session_id}</SessionID>
</FetchTokenRequest>"""
    try:
        resp = requests.post(EBAY_API_URL, data=xml.encode("utf-8"),
                             headers=_trading_api_headers("FetchToken"), timeout=15)
        root = ET.fromstring(resp.text)
        token = _xml_text(root, "eBayAuthToken")
        expiration = _xml_text(root, "HardExpirationTime")
        if token:
            _store["ebay_token"] = token
            return (f"<html><body style='font-family:monospace;padding:20px'>"
                    f"<h2>&#10003; Token Retrieved!</h2>"
                    f"<p><strong>Copy this token:</strong></p>"
                    f"<textarea rows='6' cols='90'>{token}</textarea>"
                    f"<p>Expires: {expiration}</p></body></html>")
        errors = [e.text for e in root.findall(".//{urn:ebay:apis:eBLBaseComponents}ShortMessage")]
        return jsonify({"error": "FetchToken failed", "details": errors, "raw": resp.text}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/auth/token", methods=["GET"])
def auth_token():
    token = _store.get("ebay_token")
    if token:
        return jsonify({"ebay_token": token})
    return jsonify({"error": "No token yet."}), 404


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
