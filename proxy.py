import pymysql
import random
import time
import os

from flask import Flask, request, jsonify

app = Flask(__name__)

MANAGER_HOST = os.getenv("MANAGER_IP")
WORKERS = os.getenv("WORKERS_IPS").split(",")
DB_USER = "root"
DB_PASS = "rootpass"
DB_NAME = "sakila"

FORWARDING_MODE = os.getenv("MODE", "direct")  # direct | random | custom

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


@app.route("/proxy", methods=["POST"])
def proxy():
  data = request.json
  sql = data.get("query")

  if not sql:
    return jsonify({"error": "Missing query"}), 400

  try:
    if is_write_query(sql):
      conn = get_conn(MANAGER_HOST)
    else:
      if FORWARDING_MODE == "direct":
        conn = get_conn(MANAGER_HOST)

      elif FORWARDING_MODE == "random":
        conn = get_conn(random.choice(WORKERS))

      elif FORWARDING_MODE == "custom":
        conn = get_conn(fastest_worker())

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
