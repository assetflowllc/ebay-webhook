"""
eBay Marketplace Account Deletion Notification Endpoint
Required by eBay Developer Program for all Production keysets.
https://developer.ebay.com/marketplace-account-deletion
"""

import hashlib
import json
import os
from flask import Flask, request, jsonify

app = Flask(__name__)

_DEFAULT_ENDPOINT = "https://ebay-webhook-75c6.onrender.com/ebay/marketplace-deletion"
_DEFAULT_TOKEN = "5bf2e15aab5625ad37a4cd8e4646971cbae66596a557ea1e7c095b3c8fae43f2"


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
        print(f"[eBay] challenge={challenge_code[:16]}... ep={endpoint_url} resp={challenge_response[:16]}...")
        return jsonify({"challengeResponse": challenge_response})

    data = request.get_json(silent=True) or {}
    print(f"[eBay] Account deletion notification: {json.dumps(data)}")
    return "", 200


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
