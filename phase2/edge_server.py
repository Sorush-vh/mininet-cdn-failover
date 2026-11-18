import sys
import socket
import threading
import time
import json
import gzip
from urllib.parse import urlparse, parse_qs
from http.server import BaseHTTPRequestHandler, HTTPServer
import urllib.request

CONTROLLER_UDP_IP = "10.0.0.10"
CONTROLLER_UDP_PORT = 9000
EDGE_HTTP_PORT = 80

# Cache keys: (file_name, encoding_type) -> raw bytes
cache_store = {}
cache_stats = {"hits": 0, "misses": 0}
stats_lock = threading.Lock()

EDGE_ID = sys.argv[1] if len(sys.argv) > 1 else "edge_local"
EDGE_IP = sys.argv[2] if len(sys.argv) > 2 else "127.0.0.1"

def stream_heartbeats():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
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
        
        parsed_url = urlparse(self.path)
        path = parsed_url.path
        query_params = parse_qs(parsed_url.query)

        if path == '/internal/stats':
            with stats_lock:
                payload = json.dumps(cache_stats).encode('utf-8')
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(payload)
            return

        file_name = path.lstrip('/')
        accept_encoding = self.headers.get('Accept-Encoding', '')
        use_gzip = 'gzip' in accept_encoding and (file_name.endswith('.txt') or file_name.endswith('.json'))
        encoding_key = 'gzip' if use_gzip else 'identity'

        offset = int(query_params.get('offset', [0])[0])
        length = int(query_params.get('length', [-1])[0])

        cache_key = (file_name, encoding_key)

        # Check Cache
        full_content = None
        with stats_lock:
            if cache_key in cache_store:
                cache_stats["hits"] += 1
                self.log_event("CACHE_HIT", f"Resource '{file_name}' ({encoding_key}) pulled from RAM. Hits: {cache_stats['hits']}.")
                full_content = cache_store[cache_key]

        # Fetch from Origin if Miss
        if full_content is None:
            self.log_event("CACHE_MISS", f"Resource '{file_name}' not cached locally. Querying Origin Server...")
            origin_base = "http://127.0.0.1:8080" if EDGE_IP == "127.0.0.1" else "http://10.0.0.1:80"
            upstream_url = f"{origin_base}/{file_name}"

            try:
                start_time = time.time()
                response = urllib.request.urlopen(upstream_url, timeout=3.0)
                origin_data = json.loads(response.read().decode('utf-8'))
                elapsed = (time.time() - start_time) * 1000
                
                raw_data_str = origin_data["data"]
                raw_bytes = raw_data_str.encode('utf-8')

                # Store identity version
                with stats_lock:
                    cache_store[(file_name, 'identity')] = raw_bytes

                # Gzip compress if requested
                if use_gzip:
                    compressed_bytes = gzip.compress(raw_bytes)
                    with stats_lock:
                        cache_store[(file_name, 'gzip')] = compressed_bytes
                    full_content = compressed_bytes
                else:
                    full_content = raw_bytes

                with stats_lock:
                    cache_stats["misses"] += 1

                self.log_event("CACHE_POPULATE", f"Fetched file from Origin in {elapsed:.1f}ms. Committed to cache.")
            except urllib.error.HTTPError as e:
                self.send_error(e.code, f"Origin side error: {e.reason}")
                return
            except Exception as e:
                self.log_event("ERROR", f"Failed to reach Origin: {e}")
                self.send_error(504, "Gateway Timeout: Origin unreachable")
                return

        # Slice content for Chunked requests (Offset & Length)
        if length > 0:
            sliced_data = full_content[offset : offset + length]
        else:
            sliced_data = full_content[offset:]

        self.send_response(200)
        self.send_header('Content-Type', 'application/octet-stream' if use_gzip else 'application/json')
        if use_gzip:
            self.send_header('Content-Encoding', 'gzip')
        self.send_header('Content-Length', str(len(sliced_data)))
        self.end_headers()
        self.wfile.write(sliced_data)

    def do_POST(self):
        global cache_store
        if self.path == '/internal/purge':
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            body = json.loads(post_data.decode('utf-8'))
            target_file = body.get("file")

            with stats_lock:
                keys_to_del = [k for k in cache_store.keys() if k[0] == target_file]
                for k in keys_to_del:
                    del cache_store[k]
                
                if keys_to_del:
                    self.log_event("CACHE_PURGE", f"Evicted '{target_file}' (all encodings) from RAM.")
                    self.respond_json({"status": f"Evicted {target_file}"})
                else:
                    self.log_event("CACHE_PURGE", f"Purge ignored. '{target_file}' not in RAM.")
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
    t_pulse = threading.Thread(target=stream_heartbeats, daemon=True)
    t_pulse.start()
    try:
        run_edge_server()
    except KeyboardInterrupt:
        print(f"\n[!] [{EDGE_ID}] Halting Edge execution container.")