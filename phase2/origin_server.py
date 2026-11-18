from http.server import BaseHTTPRequestHandler, HTTPServer
import socket
import json
import os
import time
import sys
import hashlib

ORIGIN_PORT = 80

LARGE_TEXT_CONTENT = ("CDN_PHASE2_TEST_DATA_LINE_" + "X" * 80 + "\n") * 5000

mock_storage = {
    "fileA.txt": "Content of File A: This is the reference data for asset A. " * 50,
    "fileB.txt": "Content of File B: This is the reference data for asset B. " * 50,
    "fileC.txt": "Content of File C: This is the reference data for asset C. " * 50,
    "large_file.txt": LARGE_TEXT_CONTENT,
}

class OriginHTTPHandler(BaseHTTPRequestHandler):
    def log_event(self, message):
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{timestamp}] [ORIGIN SERVER] {message}", flush=True)

    def log_message(self, format, *args):
        return

    def do_GET(self):
        file_name = self.path.lstrip('/')
        self.log_event(f"Incoming request received from Edge for resource: '{file_name}'")

        if file_name in mock_storage:
            content = mock_storage[file_name]
            sha256_hash = hashlib.sha256(content.encode('utf-8')).hexdigest()
            
            response_data = {
                "file": file_name,
                "data": content,
                "sha256": sha256_hash,
                "size": len(content.encode('utf-8')),
                "origin_timestamp": time.time()
            }
            
            payload = json.dumps(response_data).encode('utf-8')

            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(payload)))
            self.end_headers()
            
            self.wfile.write(payload)
            self.log_event(f"Dispatched '{file_name}' ({len(payload)} bytes, SHA256: {sha256_hash[:10]}...).")
        else:
            error_response = json.dumps({"error": "Resource not found at Origin"}).encode('utf-8')
            self.send_response(404)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(error_response)
            self.log_event(f"CRITICAL: Requested resource '{file_name}' does not exist.")

def run_server():
    server_address = ('', ORIGIN_PORT)
    httpd = HTTPServer(server_address, OriginHTTPHandler)
    print(f"[*] Origin Server active on port {ORIGIN_PORT}...", flush=True)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n[!] Shutting down Origin Server gracefully.", flush=True)
        httpd.server_close()

if __name__ == '__main__':
    ORIGIN_PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8080
    run_server()