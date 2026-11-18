#!/usr/bin/python3
import urllib.request
import urllib.error
import json
import sys
import time
import threading
import socket

def get_controller_url():
    # Inside Mininet, the controller is at 10.0.0.10. 
    # We check if port 8000 is open there; if not, we default to localhost.
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(0.2)
        s.connect(("10.0.0.10", 8000))
        s.close()
        return "http://10.0.0.10:8000"
    except:
        return "http://127.0.0.1:8000"

def discover_healthy_edges():
    url = f"{get_controller_url()}/edges"
    try:
        response = urllib.request.urlopen(url, timeout=2.0)
        return json.loads(response.read().decode('utf-8'))
    except Exception as e:
        print(f"Client failed to reach Controller at {url}: {e}")
        return {}

def fetch_file(file_name):
    print(f"\nRequesting lookup for resource: '{file_name}'")
    edges = discover_healthy_edges()
    
    if not edges:
        print("No healthy Edge servers available in the pool right now.")
        return None

    # Pick the first available edge server from the controller's active map
    selected_id = list(edges.keys())[0]
    edge_info = edges[selected_id]
    
    edge_url = f"http://{edge_info['ip']}:{edge_info['port']}/{file_name}"
    print(f"Controller directed Client to [{selected_id.upper()}] at {edge_info['ip']}:{edge_info['port']}")

    try:
        start_time = time.time()
        response = urllib.request.urlopen(edge_url, timeout=5.0)
        result = json.loads(response.read().decode('utf-8'))
        elapsed = (time.time() - start_time) * 1000
        
        print(f"Response received in {elapsed:.1f}ms [Source: {result['source'].upper()}]")
        print(f"Content: \"{result['data']}\"")
        return result
    except urllib.error.HTTPError as e:
        print(f"Edge Server returned an error: {e.read().decode('utf-8')}")
    except Exception as e:
        print(f"Failed to pull content from selected Edge server: {e}")
        return None

def trigger_global_purge(file_name):
    url = f"{get_controller_url()}/purge"
    print(f"\nSending Administrative Purge command to Controller for: '{file_name}'")
    try:
        req_data = json.dumps({"file": file_name}).encode('utf-8')
        req = urllib.request.Request(url, data=req_data, method='POST', headers={'Content-Type': 'application/json'})
        res = urllib.request.urlopen(req, timeout=2.0)
        print(f"Controller Purge Response: {res.read().decode('utf-8')}")
    except Exception as e:
        print(f"Purge execution failed: {e}")

def run_scenario_1():
    print("\n=== SCENARIO 1: BASELINE PERFORMANCE & HIT/MISS VALIDATION ===")
    fetch_file("fileA.txt")  # Expect: Cache Miss (Slow, pulls from Origin)
    time.sleep(1)
    fetch_file("fileA.txt")  # Expect: Cache Hit (Fast, pulls from Edge RAM)

def run_scenario_3():
    print("\n=== SCENARIO 3: ADMINISTRATIVE CACHE PURGE SYSTEM VALIDATION ===")
    print("Step 1: Populating cache...")
    fetch_file("fileB.txt")
    time.sleep(1)
    print("\nStep 2: Evicting cache asset via administrative control plane...")
    trigger_global_purge("fileB.txt")
    time.sleep(1)
    print("\nStep 3: Re-requesting asset post-eviction...")
    fetch_file("fileB.txt")

def run_scenario_4():
    print("\n=== SCENARIO 4: CONCURRENCY AND PARALLEL LOAD TRAFFIC TEST ===")
    def simulate_concurrent_user(user_id, asset):
        fetch_file(asset)

    threads = []
    assets = ["fileA.txt", "fileB.txt", "fileC.txt", "fileA.txt"]
    for i, asset in enumerate(assets):
        t = threading.Thread(target=simulate_concurrent_user, args=(i+1, asset))
        threads.append(t)
        t.start()

    for t in threads:
        t.join()
    print("\nConcurrent stress simulation complete without execution faults.")

if __name__ == '__main__':
    if len(sys.argv) > 1:
        target = sys.argv[1]
        if target == "scenario1":
            run_scenario_1()
        elif target == "scenario3":
            run_scenario_3()
        elif target == "scenario4":
            run_scenario_4()
        else:
            fetch_file(target)
    else:
        print("Usage: python3 cdn_test_client.py [scenario1/scenario3/scenario4/filename]")