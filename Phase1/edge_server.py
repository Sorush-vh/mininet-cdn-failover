import sys
import socket
import threading
import time
import json
from http.server import BaseHTTPRequestHandler, HTTPServer
import urllib.request

CONTROLLER_UDP_IP = "10.0.0.10"
CONTROLLER_UDP_PORT = 9000
ORIGIN_SERVER_URL = "http://10.0.0.1:80"
EDGE_HTTP_PORT = 80

cache_store = {}
cache_stats = {"hits": 0, "misses": 0}
stats_lock = threading.Lock()

EDGE_ID = sys.argv[1] if len(sys.argv) > 1 else "edge_local"
EDGE_IP = sys.argv[2] if len(sys.argv) > 2 else "127.0.0.1"

# --- 1. ASYNCHRONOUS UDP HEARTBEAT BEACON ---
def stream_heartbeats():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    #for local tests
    target_ip = "127.0.0.1" if EDGE_IP == "127.0.0.1" else CONTROLLER_UDP_IP
    server_target = (target_ip, CONTROLLER_UDP_PORT)
    
    print(f"[*] [{EDGE_ID}] Pulse beacon thread initialized targeting {target_ip}:{CONTROLLER_UDP_PORT}.", flush=True)
    while True:
        try:
            payload = {
                "edge_id": EDGE_ID,
                "http_port": EDGE_HTTP_PORT
            }
            raw_bytes = json.dumps(payload).encode('utf-8')
            sock.sendto(raw_bytes, server_target)
        except Exception as e:
            print(f"[!] [{EDGE_ID}] Pulse error: {e}", flush=True)
        time.sleep(1.0)

class EdgeHTTPHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args): return

    def log_event(self, context, message):
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{timestamp}] [{EDGE_ID.upper()}] [{context}] {message}", flush=True)

    def do_GET(self):
        global cache_store
        
        if self.path == '/internal/stats':
            with stats_lock:
                payload = json.dumps(cache_stats).encode('utf-8')
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(payload)
            return

        file_name = self.path.lstrip('/')
        
        with stats_lock:
            if file_name in cache_store:
                cache_stats["hits"] += 1
                self.log_event("CACHE_HIT", f"Resource '{file_name}' pulled instantly from RAM. Hit count: {cache_stats['hits']}.")
                content = cache_store[file_name]
                self.respond_json({"source": "edge_cache", "file": file_name, "data": content})
                return

        self.log_event("CACHE_MISS", f"Resource '{file_name}' not found locally. Initiating upstream proxy query to Origin Server...")
        origin_base = "http://127.0.0.1:8080" if EDGE_IP == "127.0.0.1" else "http://10.0.0.1:80"
        upstream_url = f"{origin_base}/{file_name}"

        try:
            # Cross high-latency link to populate local cache
            start_time = time.time()
            response = urllib.request.urlopen(upstream_url, timeout=3.0)
            origin_data = json.loads(response.read().decode('utf-8'))
            elapsed = (time.time() - start_time) * 1000
            
            file_content = origin_data["data"]
            
            with stats_lock:
                cache_stats["misses"] += 1
                cache_store[file_name] = file_content # Populate memory database
                
            self.log_event("CACHE_POPULATE", f"Fetched file from Origin in {elapsed:.1f}ms. Committed to local memory cache.")
            self.respond_json({"source": "edge_proxy_fetch", "file": file_name, "data": file_content})
            
        except urllib.error.HTTPError as e:
            self.send_error(e.code, f"Origin side error: {e.reason}")
        except Exception as e:
            self.log_event("ERROR", f"Failed to synchronize with Upstream Origin: {e}")
            self.send_error(504, "Gateway Timeout: Origin server unreachable")

    def do_POST(self):
        global cache_store
        if self.path == '/internal/purge':
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            body = json.loads(post_data.decode('utf-8'))
            target_file = body.get("file")

            with stats_lock:
                if target_file in cache_store:
                    del cache_store[target_file]
                    self.log_event("CACHE_PURGE", f"Successfully evicted '{target_file}' from memory on administrative instruction.")
                    self.respond_json({"status": f"Evicted {target_file}"})
                else:
                    self.log_event("CACHE_PURGE", f"Purge command ignored. '{target_file}' does not exist inside memory.")
                    self.respond_json({"status": "Not found"})
        else:
            self.send_error(404)

    def respond_json(self, data_dict):
        raw_bytes = json.dumps(data_dict).encode('utf-8')
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(raw_bytes)))
        self.end_headers()
        self.wfile.write(raw_bytes)

def run_edge_server():
    server_address = ('', EDGE_HTTP_PORT)
    httpd = HTTPServer(server_address, EdgeHTTPHandler)
    print(f"[*] [{EDGE_ID}] HTTP Proxy Service handling traffic on port {EDGE_HTTP_PORT}...", flush=True)
    httpd.serve_forever()

if __name__ == '__main__':
    # Fire heartbeats down the UDP tracking pipeline
    t_pulse = threading.Thread(target=stream_heartbeats, daemon=True)
    t_pulse.start()

    try:
        run_edge_server()
    except KeyboardInterrupt:
        print(f"\n[!] [{EDGE_ID}] Halting Edge execution container.")