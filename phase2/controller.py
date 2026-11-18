import socket
import threading
import time
import json
from http.server import BaseHTTPRequestHandler, HTTPServer
import urllib.request

CONTROLLER_HTTP_PORT = 8000
CONTROLLER_UDP_PORT = 9000
HEARTBEAT_TIMEOUT = 4.0

# Shared Thread-Safe Database
active_edges = {}
edge_lock = threading.Lock()

def udp_heartbeat_listener():
    udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    udp_sock.bind(('', CONTROLLER_UDP_PORT))
    print(f"[*] UDP Heartbeat Monitor active on port {CONTROLLER_UDP_PORT}...", flush=True)

    while True:
        try:
            data, addr = udp_sock.recvfrom(1024)
            payload = json.loads(data.decode('utf-8'))
            
            edge_id = payload.get("edge_id")
            edge_ip = addr[0]
            edge_http_port = payload.get("http_port", 80)

            with edge_lock:
                if edge_id not in active_edges:
                    print(f"\n[+] [CONTROLLER] New Edge Server discovered: '{edge_id}' discovered at IP {edge_ip}", flush=True)
                
                active_edges[edge_id] = {
                    "ip": edge_ip,
                    "port": edge_http_port,
                    "last_seen": time.time()
                }
        except Exception as e:
            print(f"[!] UDP Error encountered: {e}", flush=True)

def fault_detection_daemon():
    while True:
        time.sleep(1.0)
        now = time.time()
        dead_nodes = []

        with edge_lock:
            for edge_id, info in active_edges.items():
                if now - info["last_seen"] > HEARTBEAT_TIMEOUT:
                    dead_nodes.append(edge_id)

            for edge_id in dead_nodes:
                print(f"\n[-] [CONTROLLER CRITICAL] Edge Server '{edge_id}' stopped sending heartbeats! Removing from healthy pool.", flush=True)
                del active_edges[edge_id]

class ControllerHTTPHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args): return

    def log_event(self, message):
        print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [CONTROLLER API] {message}", flush=True)

    def do_GET(self):
        if self.path == '/edges':
            with edge_lock:
                pool = {eid: {"ip": info["ip"], "port": info["port"]} for eid, info in active_edges.items()}
            
            payload = json.dumps(pool).encode('utf-8')
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        elif self.path == '/cache':
            self.log_event("Scraping cluster-wide performance and cache statistics...")
            aggregated_stats = {}
            
            with edge_lock:
                current_edges = list(active_edges.items())

            for edge_id, info in current_edges:
                try:
                    url = f"http://{info['ip']}:{info['port']}/internal/stats"
                    req = urllib.request.urlopen(url, timeout=1.0)
                    aggregated_stats[edge_id] = json.loads(req.read().decode('utf-8'))
                except Exception:
                    aggregated_stats[edge_id] = "Unreachable/Error"

            payload = json.dumps(aggregated_stats).encode('utf-8')
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(payload)
        
        else:
            self.send_error(404, "Endpoint not found")

    def do_POST(self):
        if self.path == '/purge':
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            body = json.loads(post_data.decode('utf-8'))
            target_file = body.get("file")

            if not target_file:
                self.send_error(400, "Missing 'file' parameter in POST body")
                return

            self.log_event(f"CRITICAL COMMAND: Broad-evicting file '{target_file}' from all active caches.")

            with edge_lock:
                current_edges = list(active_edges.items())

            for edge_id, info in current_edges:
                try:
                    url = f"http://{info['ip']}:{info['port']}/internal/purge"
                    req_data = json.dumps({"file": target_file}).encode('utf-8')
                    req = urllib.request.Request(url, data=req_data, method='POST', headers={'Content-Type': 'application/json'})
                    urllib.request.urlopen(req, timeout=1.0)
                except Exception as e:
                    self.log_event(f"Failed to forward purge request to {edge_id}: {e}")

            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"status": "Global purge commands executed successfully"}).encode('utf-8'))
        else:
            self.send_error(404, "Endpoint not found")

def run_http_server():
    server_address = ('', CONTROLLER_HTTP_PORT)
    httpd = HTTPServer(server_address, ControllerHTTPHandler)
    print(f"[*] HTTP Administrative API active on port {CONTROLLER_HTTP_PORT}...", flush=True)
    httpd.serve_forever()

if __name__ == '__main__':
    t_udp = threading.Thread(target=udp_heartbeat_listener, daemon=True)
    t_fault = threading.Thread(target=fault_detection_daemon, daemon=True)
    
    t_udp.start()
    t_fault.start()

    try:
        run_http_server()
    except KeyboardInterrupt:
        print("\n[!] Shutting down Controller gracefully.")