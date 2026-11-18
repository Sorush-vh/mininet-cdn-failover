from http.server import BaseHTTPRequestHandler, HTTPServer
import socket
import json
import os
import time
import sys

ORIGIN_PORT = 80

class OriginHTTPHandler(BaseHTTPRequestHandler):
    def log_event(self, message):
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{timestamp}] [ORIGIN SERVER] {message}", flush=True)

    def log_message(self, format, *args):
        return

    def do_GET(self):
        # Extract file name from request path
        file_name = self.path.lstrip('/')
        
        self.log_event(f"Incoming request received from Edge for resource: '{file_name}'")

        # Define mock file database directory
        mock_storage = {
            "fileA.txt": "Content of File A: This is the reference data for asset A.",
            "fileB.txt": "Content of File B: This is the reference data for asset B.",
            "fileC.txt": "Content of File C: This is the reference data for asset C."
        }

        if file_name in mock_storage:
            content = mock_storage[file_name]
            response_data = {
                "file": file_name,
                "data": content,
                "origin_timestamp": time.time()
            }
            
            payload = json.dumps(response_data).encode('utf-8')

            # Build and send standard HTTP response headers
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(payload)))
            self.end_headers()
            
            # Flush payload down the socket interface
            self.wfile.write(payload)
            self.log_event(f"Successful cache synchronization. Dispatched '{file_name}' to requesting Edge Node.")
        else:
            # Resource not found error path
            error_response = json.dumps({"error": "Resource not found at Origin"}).encode('utf-8')
            self.send_response(404)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(error_response)
            self.log_event(f"CRITICAL: Requested resource '{file_name}' does not exist inside Master storage lookup.")

def run_server():
    server_address = ('', ORIGIN_PORT)
    httpd = HTTPServer(server_address, OriginHTTPHandler)
    print(f"[*] Origin Server active and listening on channel port {ORIGIN_PORT}...", flush=True)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n[!] Shutting down Origin Server instance gracefully.", flush=True)
        httpd.server_close()

if __name__ == '__main__':
    ORIGIN_PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8080
    run_server()