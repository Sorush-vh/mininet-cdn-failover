#!/usr/bin/python3
import urllib.request
import urllib.error
import json
import sys
import time
import uuid
import hashlib
import gzip
import socket

CHUNK_SIZE = 65536  # 64 KB

def get_controller_url():
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
        print(f"[CLIENT ERROR] Failed to reach Controller: {e}")
        return {}

def fetch_chunked_file(file_name, enable_gzip=True, simulate_failover_at=None):
    session_id = str(uuid.uuid4())[:8]
    print(f"\n=======================================================")
    print(f"[*] Starting Chunked Download Session [{session_id}] for: '{file_name}'")
    print(f"[*] Gzip Enabled: {enable_gzip}")
    print(f"=======================================================")

    edges = discover_healthy_edges()
    if not edges:
        print("[!] No healthy Edge servers available.")
        return None

    edge_keys = sorted(list(edges.keys()))
    current_edge_id = edge_keys[0]
    current_edge_info = edges[current_edge_id]

    received_bytes = bytearray()
    offset = 0
    total_bytes_downloaded = 0
    recovery_time = 0
    start_time = time.time()
    
    failover_simulated = False
    failed_ip = None

    while True:
        # Simulate edge failure ONLY ONCE during test scenario
        if simulate_failover_at is not None and offset >= simulate_failover_at and not failover_simulated and len(edge_keys) > 1:
            print(f"\n[SIMULATION] Simulated failure on [{current_edge_id.upper()}] at offset {offset}!")
            failed_ip = current_edge_info['ip']
            current_edge_info = {"ip": "10.0.0.254", "port": 80} # Dead IP to trigger timeout
            failover_simulated = True

        url = f"http://{current_edge_info['ip']}:{current_edge_info['port']}/{file_name}?offset={offset}&length={CHUNK_SIZE}"
        
        req = urllib.request.Request(url)
        if enable_gzip:
            req.add_header('Accept-Encoding', 'gzip')

        try:
            chunk_start = time.time()
            with urllib.request.urlopen(req, timeout=2.5) as resp:
                raw_data = resp.read()
                is_gzipped = resp.headers.get('Content-Encoding') == 'gzip'
                
                if is_gzipped:
                    data = gzip.decompress(raw_data)
                else:
                    data = raw_data

                total_bytes_downloaded += len(raw_data)
                
                if not data:
                    print(f"[*] Reached End-of-File at offset {offset}.")
                    break

                received_bytes.extend(data)
                chunk_len = len(data)
                offset += chunk_len

                print(f"  --> Chunk [Offset: {offset - chunk_len} -> {offset}] ({len(raw_data)} bytes on wire) pulled from [{current_edge_id.upper()}]")

                if chunk_len < CHUNK_SIZE:
                    print(f"[*] Final partial chunk received. Download complete.")
                    break

        except Exception as e:
            # --- CHALLENGE 1: FAILOVER & RESUMPTION LOGIC ---
            fail_time = time.time()
            print(f"\n[!] [FAILOVER TRIGGERED] Edge [{current_edge_id.upper()}] failed at offset {offset}! Error: {e}")
            print(f"[*] Querying Controller for new healthy Edge node...")
            
            time.sleep(0.5)
            active_edges = discover_healthy_edges()
            
            # Exclude the edge that failed
            ip_to_exclude = failed_ip if (failover_simulated and failed_ip) else current_edge_info['ip']
            valid_edges = {k: v for k, v in active_edges.items() if v['ip'] != ip_to_exclude}
            
            if not valid_edges:
                print("[CRITICAL] Failover failed: No alternative healthy Edge nodes found!")
                return None

            # Migrate to new Edge
            new_edge_id = sorted(list(valid_edges.keys()))[0]
            current_edge_info = valid_edges[new_edge_id]
            current_edge_id = new_edge_id
            
            recovery_time = (time.time() - fail_time) * 1000
            print(f"[SUCCESS] Migrated Session [{session_id}] to [{current_edge_id.upper()}] ({current_edge_info['ip']}). Resuming from offset {offset} (Recovery Time: {recovery_time:.1f}ms)\n")
            continue

    total_time = (time.time() - start_time) * 1000
    assembled_data = bytes(received_bytes)
    file_checksum = hashlib.sha256(assembled_data).hexdigest()

    print(f"\n--- SESSION METRICS & VALIDATION ---")
    print(f"• Total Data Size (Uncompressed) : {len(assembled_data)} bytes")
    print(f"• Total Data Transferred on Wire : {total_bytes_downloaded} bytes")
    if len(assembled_data) > 0:
        compression_ratio = (1 - (total_bytes_downloaded / len(assembled_data))) * 100
        print(f"• Bandwidth Reduction (Gzip)     : {compression_ratio:.1f}%")
    print(f"• Total Session Download Time    : {total_time:.1f} ms")
    if recovery_time > 0:
        print(f"• Migration / Failover Recovery  : {recovery_time:.1f} ms")
    print(f"• Calculated SHA256 Checksum     : {file_checksum}")
    
    return assembled_data

def run_challenge_1_demo():
    print("\n=== DEMO CHALLENGE 1: SESSION MIGRATION & FAILOVER ===")
    fetch_chunked_file("large_file.txt", enable_gzip=False, simulate_failover_at=131072)

def run_challenge_5_demo():
    print("\n=== DEMO CHALLENGE 5: CONTENT COMPRESSION (GZIP) ===")
    print("\n---> Test A: Normal Transfer (Identity)")
    fetch_chunked_file("large_file.txt", enable_gzip=False)
    
    time.sleep(1)
    print("\n---> Test B: Compressed Transfer (Gzip)")
    fetch_chunked_file("large_file.txt", enable_gzip=True)

if __name__ == '__main__':
    if len(sys.argv) > 1:
        cmd = sys.argv[1]
        if cmd == "challenge1":
            run_challenge_1_demo()
        elif cmd == "challenge5":
            run_challenge_5_demo()
        else:
            fetch_chunked_file(cmd)
    else:
        print("Usage: python3 client.py [challenge1 / challenge5 / filename]")