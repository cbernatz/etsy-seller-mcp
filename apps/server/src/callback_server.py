"""HTTP callback server for OAuth redirect handling."""

import asyncio
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse, parse_qs
from typing import Optional, Callable
import threading


class CallbackHandler(BaseHTTPRequestHandler):
    """HTTP request handler for OAuth callbacks."""
    
    callback_function: Optional[Callable] = None
    
    def log_message(self, format, *args):
        """Suppress default logging."""
        pass
    
    def do_GET(self):
        """Handle GET request (OAuth callback)."""
        parsed_url = urlparse(self.path)
        query_params = parse_qs(parsed_url.query)
        
        # Extract authorization code and state
        code = query_params.get('code', [None])[0]
        state = query_params.get('state', [None])[0]
        error = query_params.get('error', [None])[0]
        
        if error:
            # OAuth error
            self.send_response(400)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            html = f"""
            <html>
            <head><title>Authorization Failed</title></head>
            <body>
                <h1>Authorization Failed</h1>
                <p>Error: {error}</p>
                <p>You can close this window.</p>
            </body>
            </html>
            """
            self.wfile.write(html.encode())
            
            if self.callback_function:
                self.callback_function(None, None, error)
        
        elif code:
            # Success - got authorization code
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            html = """
            <html>
            <head><title>Authorization Successful</title></head>
            <body>
                <h1>Authorization Successful!</h1>
                <p>You can close this window and return to your application.</p>
                <script>window.close();</script>
            </body>
            </html>
            """
            self.wfile.write(html.encode())
            
            if self.callback_function:
                self.callback_function(code, state, None)
        
        else:
            # No code or error - invalid request
            self.send_response(400)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            html = """
            <html>
            <head><title>Invalid Request</title></head>
            <body>
                <h1>Invalid Request</h1>
                <p>Missing authorization code.</p>
            </body>
            </html>
            """
            self.wfile.write(html.encode())


class OAuthCallbackServer:
    """Simple HTTP server for OAuth callback handling."""
    
    def __init__(self, host: str = "localhost", port: int = 8477):
        """
        Initialize callback server.
        
        Args:
            host: Host to bind to
            port: Port to listen on
        """
        self.host = host
        self.port = port
        self.server: Optional[HTTPServer] = None
        self.server_thread: Optional[threading.Thread] = None
        self.callback_data: dict = {}
        self.callback_received = threading.Event()
    
    def _handle_callback(self, code: Optional[str], state: Optional[str], error: Optional[str]):
        """
        Internal callback handler.
        
        Args:
            code: Authorization code
            state: State parameter
            error: Error message if any
        """
        self.callback_data = {
            "code": code,
            "state": state,
            "error": error
        }
        self.callback_received.set()
    
    def start(self) -> None:
        """Start the callback server in a background thread."""
        CallbackHandler.callback_function = self._handle_callback
        
        self.server = HTTPServer((self.host, self.port), CallbackHandler)
        self.server_thread = threading.Thread(target=self.server.serve_forever)
        self.server_thread.daemon = True
        self.server_thread.start()
    
    def wait_for_callback(self, timeout: float = 300.0) -> dict:
        """
        Wait for OAuth callback to be received.
        
        Args:
            timeout: Timeout in seconds (default 5 minutes)
        
        Returns:
            Dictionary containing code, state, and error
        
        Raises:
            TimeoutError: If callback not received within timeout
        """
        if self.callback_received.wait(timeout):
            return self.callback_data
        else:
            raise TimeoutError("OAuth callback not received within timeout period")
    
    def stop(self) -> None:
        """Stop the callback server."""
        if self.server:
            self.server.shutdown()
            self.server.server_close()
        if self.server_thread:
            self.server_thread.join(timeout=5)

