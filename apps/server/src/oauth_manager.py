"""OAuth 2.0 manager for Etsy API authentication with PKCE.

This manager handles session-based authentication only. Tokens are not persisted
or automatically refreshed - users must reconnect when the session ends.
"""

import os
import hashlib
import base64
import secrets
import httpx
from typing import Optional, Dict, Any
from datetime import datetime, timedelta


class OAuthManager:
    """Manages OAuth 2.0 flow with PKCE for Etsy API."""
    
    AUTHORIZE_URL = "https://www.etsy.com/oauth/connect"
    TOKEN_URL = "https://api.etsy.com/v3/public/oauth/token"
    
    def __init__(self, api_key: Optional[str] = None, redirect_uri: Optional[str] = None):
        """
        Initialize OAuth manager.
        
        Args:
            api_key: Etsy API key (keystring). If not provided, reads from ETSY_API_KEY env var.
            redirect_uri: OAuth redirect URI. Defaults to http://localhost:8477/callback
        """
        self.api_key = api_key or os.getenv("ETSY_API_KEY")
        if not self.api_key:
            raise ValueError("ETSY_API_KEY is required. Set it as an environment variable.")
        
        self.redirect_uri = redirect_uri or "http://localhost:8477/callback"
        self.code_verifier: Optional[str] = None
        self.state: Optional[str] = None
    
    def generate_pkce_pair(self) -> tuple[str, str]:
        """
        Generate PKCE code verifier and challenge.
        
        Returns:
            Tuple of (code_verifier, code_challenge)
        """
        # Generate code verifier (43-128 characters)
        code_verifier = base64.urlsafe_b64encode(secrets.token_bytes(32)).decode('utf-8').rstrip('=')
        
        # Generate code challenge (SHA256 hash of verifier)
        challenge_bytes = hashlib.sha256(code_verifier.encode('utf-8')).digest()
        code_challenge = base64.urlsafe_b64encode(challenge_bytes).decode('utf-8').rstrip('=')
        
        return code_verifier, code_challenge
    
    def get_authorization_url(self, scopes: list[str]) -> Dict[str, str]:
        """
        Generate the authorization URL for the OAuth flow.
        
        Args:
            scopes: List of Etsy API scopes to request (e.g., ['shops_r', 'listings_r'])
        
        Returns:
            Dictionary containing:
            - url: The authorization URL to redirect the user to
            - state: State parameter for CSRF protection
            - code_verifier: Code verifier to store for token exchange
        """
        # Generate PKCE pair
        self.code_verifier, code_challenge = self.generate_pkce_pair()
        
        # Generate state for CSRF protection
        self.state = secrets.token_urlsafe(32)
        
        # Build authorization URL
        scope_string = " ".join(scopes)
        params = {
            "response_type": "code",
            "client_id": self.api_key,
            "redirect_uri": self.redirect_uri,
            "scope": scope_string,
            "state": self.state,
            "code_challenge": code_challenge,
            "code_challenge_method": "S256"
        }
        
        query_string = "&".join([f"{k}={httpx.QueryParams({k: v}).get(k)}" for k, v in params.items()])
        auth_url = f"{self.AUTHORIZE_URL}?{query_string}"
        
        return {
            "url": auth_url,
            "state": self.state,
            "code_verifier": self.code_verifier
        }
    
    async def exchange_code_for_token(self, code: str, code_verifier: str) -> Dict[str, Any]:
        """
        Exchange authorization code for access token.
        
        Args:
            code: Authorization code from callback
            code_verifier: PKCE code verifier
        
        Returns:
            Dictionary containing:
            - access_token: The access token (session-based)
            - expires_at: Token expiration timestamp (ISO format)
            - token_type: Token type (usually "Bearer")
        
        Raises:
            httpx.HTTPError: If token exchange fails
        """
        async with httpx.AsyncClient() as client:
            response = await client.post(
                self.TOKEN_URL,
                data={
                    "grant_type": "authorization_code",
                    "client_id": self.api_key,
                    "redirect_uri": self.redirect_uri,
                    "code": code,
                    "code_verifier": code_verifier
                },
                headers={
                    "Content-Type": "application/x-www-form-urlencoded"
                }
            )
            response.raise_for_status()
            
            data = response.json()
            
            # Calculate expiration time
            expires_in = data.get("expires_in", 3600)  # Default 1 hour
            expires_at = (datetime.utcnow() + timedelta(seconds=expires_in)).isoformat()
            
            return {
                "access_token": data["access_token"],
                "expires_at": expires_at,
                "token_type": data.get("token_type", "Bearer")
            }

