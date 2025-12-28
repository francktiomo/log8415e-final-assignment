import pymysql
import random
import time
import os

from collections import Counter
from flask import Flask, request, jsonify

app = Flask(__name__)

MANAGER_HOST = os.getenv("MANAGER_IP")
WORKERS = os.getenv("WORKERS_IPS").split(",")
DB_USER = "root"
DB_PASS = "rootpass"
DB_NAME = "sakila"

MODE = "direct"
stats = Counter()

def get_conn(host):
  return pymysql.connect(
    host=host,
    user=DB_USER,
    password=DB_PASS,
    database=DB_NAME
  )


def is_write_query(query: str) -> bool:
  q = query.strip().lower()
  return q.startswith("insert") or q.startswith("update") or q.startswith("delete") or q.startswith("create")


def fastest_worker():
  best = None
  best_time = 99999

  for host in WORKERS:
    start = time.time()
    try:
      conn = get_conn(host)
      conn.close()
      latency = time.time() - start
      if latency < best_time:
        best_time = latency
        best = host
    except:
      continue

  return best or random.choice(WORKERS)


def get_hostname(host):
  hostname = ''
  if host == MANAGER_HOST:
    hostname = 'manager'
  elif host == WORKERS[0]:
      hostname = 'worker1'
  else:
    hostname = 'worker2'

  return hostname


@app.route("/set_mode", methods=["POST"])
def set_mode():
  global MODE

  body = request.json
  mode = body.get("mode", "").lower()

  if mode not in ["direct", "random", "custom"]:
      return jsonify({"error": "Invalid mode"}), 400

  MODE = mode
  return jsonify({"message": "mode updated", "mode": MODE}), 200


@app.route("/stats")
def get_stats():
  global stats    
  result = jsonify({
    "mode": MODE,
    "hits": dict(stats)
  })
  stats = Counter()
  return result


@app.route("/query", methods=["POST"])
def query():
  global MODE

  data = request.json
  sql = data.get("query")

  if not sql:
    return jsonify({"error": "Missing query"}), 400

  try:
    target_host = None
    if is_write_query(sql):
      target_host = MANAGER_HOST
    else:
      if MODE == "direct":
        target_host = MANAGER_HOST

      elif MODE == "random":
        target_host = random.choice(WORKERS)

      elif MODE == "custom":
        target_host = fastest_worker()
    
    hostname = get_hostname(target_host)
    stats[f'{target_host} ({hostname})'] += 1

    conn = get_conn(target_host)

    cur = conn.cursor()
    cur.execute(sql)

    if is_write_query(sql):
      conn.commit()

    result = cur.fetchall()
    conn.close()

    return jsonify({"result": result}), 200

  except Exception as e:
    return jsonify({"error": str(e)}), 500


app.run(host="0.0.0.0", port=5000)
