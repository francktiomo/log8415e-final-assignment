import requests
import re
import os

from flask import Flask, request, jsonify

app = Flask(__name__)

PROXY_URL = os.getenv("PROXY_URL")
API_KEY = os.getenv("API_KEY", "secret123")


DANGEROUS = [
    r"drop\s+table",
    r"delete\s+from\s+\w+\s*$",
    r"truncate",
    r"shutdown",
]


@app.route("/stats")
def get_stats():
  key = request.headers.get("x-api-key")
  if key != API_KEY:
    return jsonify({"error": "Unauthorized"}), 403

  resp = requests.get(f"{PROXY_URL}/stats").json()
  return jsonify(resp)


def is_safe(sql):
  lower = sql.lower()
  for d in DANGEROUS:
    if re.search(d, lower):
      return False
  return True


@app.route("/set_mode", methods=["POST"])
def set_mode():
  key = request.headers.get("x-api-key")
  if key != API_KEY:
    return jsonify({"error": "Unauthorized"}), 403

  body = request.json
  mode = body.get("mode", "")

  resp = requests.post(f"{PROXY_URL}/set_mode", json={"mode": mode}).json()
  return jsonify(resp)


@app.route("/query", methods=["POST"])
def handle_request():
    headers = request.headers
    key = headers.get("x-api-key")

    if key != API_KEY:
      return jsonify({"error": "Unauthorized"}), 403

    body = request.json
    sql = body.get("query")

    if not sql:
      return jsonify({"error": "No query provided"}), 400

    if not is_safe(sql):
      return jsonify({"error": "Unsafe query"}), 400

    resp = requests.post(f"{PROXY_URL}/query", json={"query": sql}).json()
    return jsonify(resp)


app.run(host="0.0.0.0", port=5000)
