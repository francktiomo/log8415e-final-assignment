import random
import requests
import time


NUMBER_OF_REQS = 1000
NUMBER_OF_ACTORS = 200
HEADERS = {"x-api-key": "secret123"}

def run_benchmark(gatekeeper_ip: str) -> None:
  """
  Run benchmark on the cluster.
  
  Args:
    gatekeeper_ip (str): IP of the gatekeeper on which to run the becnhmark
  """
  global NUMBER_OF_ACTORS

  proxy_strategies = ['direct', 'random', 'custom']
  gatekeeper_url = f"http://{gatekeeper_ip}:5000/query"

  for mode in proxy_strategies:
    print(f"\n===== Benchmarking with proxy strategy: {mode.upper()} =====")

    results = {
      "read_latencies": [],
      "write_latencies": []
    }

    # Set mode
    resp = requests.post(
      f"http://{gatekeeper_ip}:5000/set_mode",
      headers=HEADERS,
      json={"mode": mode}
    )

    # WRITES
    print('WRITES')
    for i in range(NUMBER_OF_REQS):
      sql = f"INSERT INTO actor(actor_id, first_name, last_name, last_update) VALUES ({NUMBER_OF_ACTORS+i}, 'TEST','USER', NOW());"
      start = time.time()

      r = requests.post(gatekeeper_url, headers=HEADERS, json={"query": sql})
      results["write_latencies"].append(time.time() - start)
    
    NUMBER_OF_ACTORS += NUMBER_OF_REQS

    # READS
    print('READS')
    for i in range(NUMBER_OF_REQS):
      actor_id = random.randint(1, NUMBER_OF_ACTORS)
      sql = f"SELECT * FROM actor WHERE actor_id={actor_id};"

      start = time.time()
      r = requests.post(gatekeeper_url, headers=HEADERS, json={"query": sql})
      results["read_latencies"].append(time.time() - start)

    def summarize(arr):
      return {
        "avg": sum(arr)/len(arr),
        "max": max(arr),
        "min": min(arr)
      }

    read_summary = summarize(results["read_latencies"])
    write_summary = summarize(results["write_latencies"])
    stats = requests.get(f'http://{gatekeeper_ip}:5000/stats', headers=HEADERS)

    print("READ performance:", read_summary)
    print("WRITE performance:", write_summary)
    print(stats.json())

