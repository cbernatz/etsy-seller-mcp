"""Etsy API client wrapper for making authenticated requests."""

import os
import httpx
from typing import Any, Dict, Optional
import asyncio


class EtsyClient:
    """Client for interacting with Etsy's API v3."""
    
    BASE_URL = "https://openapi.etsy.com/v3"
    
    def __init__(
        self, 
        api_key: Optional[str] = None, 
        access_token: Optional[str] = None
    ):
        """
        Initialize the Etsy API client.
        
        Args:
            api_key: Etsy API key (keystring). If not provided, reads from ETSY_API_KEY env var.
            access_token: OAuth 2.0 access token (required, session-based only).
        
        Raises:
            ValueError: If credentials are not provided.
        """
        self.api_key = api_key or os.getenv("ETSY_API_KEY")
        
        if not self.api_key:
            raise ValueError("ETSY_API_KEY is required. Set it as an environment variable.")
        
        # Access token must be provided (session-based, not stored)
        self.access_token = access_token
        
        if not self.access_token:
            raise ValueError("No access token provided. Please use connect_etsy to authenticate.")
        
        self.client = httpx.Client(timeout=30.0)
        self.async_client = httpx.AsyncClient(timeout=30.0)
    
    def _get_headers(self) -> Dict[str, str]:
        """Get the authentication headers for API requests."""
        return {
            "x-api-key": self.api_key,
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
        }
    
    async def get_current_user(self) -> Dict[str, Any]:
        """
        Get information about the currently authenticated user.
        
        Returns:
            Dictionary containing user details including user_id and shop_id.
        
        Raises:
            httpx.HTTPError: If the API request fails.
        """
        url = f"{self.BASE_URL}/application/users/me"
        response = await self.async_client.get(url, headers=self._get_headers())
        response.raise_for_status()
        return response.json()
    
    async def get_user_shops(self, user_id: str) -> Dict[str, Any]:
        """
        Get shops owned by a user.
        
        Args:
            user_id: The numeric user ID.
        
        Returns:
            Dictionary containing list of shops.
        
        Raises:
            httpx.HTTPError: If the API request fails.
        """
        url = f"{self.BASE_URL}/application/users/{user_id}/shops"
        response = await self.async_client.get(url, headers=self._get_headers())
        response.raise_for_status()
        return response.json()
    
    async def get_shop(self, shop_id: str) -> Dict[str, Any]:
        """
        Get shop information by shop ID.
        
        Args:
            shop_id: The unique identifier for the shop.
        
        Returns:
            Dictionary containing shop details.
        
        Raises:
            httpx.HTTPError: If the API request fails.
        """
        url = f"{self.BASE_URL}/application/shops/{shop_id}"
        response = await self.async_client.get(url, headers=self._get_headers())
        response.raise_for_status()
        return response.json()
    
    async def get_shop_listings(
        self, 
        shop_id: str, 
        state: Optional[str] = "active",
        limit: int = 25,
        offset: int = 0
    ) -> Dict[str, Any]:
        """
        Get listings for a shop.
        
        Args:
            shop_id: The unique identifier for the shop.
            state: Filter by listing state. Options: 'active', 'inactive', 'draft', 
                   'expired', 'sold_out'. Default is 'active'.
            limit: Number of results to return (max 100). Default is 25.
            offset: Offset for pagination. Default is 0.
        
        Returns:
            Dictionary containing listings array and pagination info.
        
        Raises:
            httpx.HTTPError: If the API request fails.
        """
        url = f"{self.BASE_URL}/application/shops/{shop_id}/listings"
        params = {
            "limit": limit,
            "offset": offset
        }
        if state:
            params["state"] = state
        
        response = await self.async_client.get(url, headers=self._get_headers(), params=params)
        response.raise_for_status()
        return response.json()
    
    async def search_shop_listings(
        self, 
        shop_id: str, 
        keywords: Optional[str] = None,
        limit: int = 25,
        offset: int = 0
    ) -> Dict[str, Any]:
        """
        Search active listings in a shop by keywords.
        
        Args:
            shop_id: The unique identifier for the shop.
            keywords: Search term or phrase to filter listings. If not provided,
                      returns all active listings.
            limit: Number of results to return (max 100). Default is 25.
            offset: Offset for pagination. Default is 0.
        
        Returns:
            Dictionary containing listings array and pagination info.
        
        Raises:
            httpx.HTTPError: If the API request fails.
        """
        url = f"{self.BASE_URL}/application/shops/{shop_id}/listings/active"
        params = {
            "limit": limit,
            "offset": offset
        }
        if keywords:
            params["keywords"] = keywords
        
        response = await self.async_client.get(url, headers=self._get_headers(), params=params)
        response.raise_for_status()
        return response.json()
    
    async def update_listing(
        self, 
        shop_id: str,
        listing_id: str, 
        legacy: bool = False,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Update a listing's properties.
        
        Args:
            shop_id: The unique identifier for the shop.
            listing_id: The numeric ID of the listing to update.
            **kwargs: Properties to update (e.g., state='active', title='New Title', etc.)
        
        Returns:
            Dictionary containing the updated listing information.
        
        Raises:
            httpx.HTTPError: If the API request fails.
        """
        url = f"{self.BASE_URL}/application/shops/{shop_id}/listings/{listing_id}"
        if legacy:
            # Enable processing profiles fields per Etsy API docs
            url = f"{url}?legacy=true"
        
        # Filter out None values
        data = {k: v for k, v in kwargs.items() if v is not None}
        
        # updateListing expects application/x-www-form-urlencoded format per Etsy API docs
        headers = {
            "x-api-key": self.api_key,
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/x-www-form-urlencoded",
        }
        
        response = await self.async_client.patch(url, headers=headers, data=data)
        response.raise_for_status()
        return response.json()

    async def get_processing_profiles(
        self,
        shop_id: str,
        limit: int = 25,
        offset: int = 0
    ) -> Dict[str, Any]:
        """
        Retrieve Processing Profiles (Readiness State Definitions) for a shop.
        """
        url = f"{self.BASE_URL}/application/shops/{shop_id}/readiness-state-definitions"
        params = {
            "limit": limit,
            "offset": offset,
        }
        response = await self.async_client.get(url, headers=self._get_headers(), params=params)
        response.raise_for_status()
        return response.json()

    async def get_processing_profile(
        self,
        shop_id: str,
        readiness_state_definition_id: str
    ) -> Dict[str, Any]:
        """
        Retrieve a single Processing Profile by ID.
        """
        url = (
            f"{self.BASE_URL}/application/shops/{shop_id}/readiness-state-definitions/"
            f"{readiness_state_definition_id}"
        )
        response = await self.async_client.get(url, headers=self._get_headers())
        response.raise_for_status()
        return response.json()

    async def create_processing_profile(
        self,
        shop_id: str,
        readiness_state: str,
        min_processing_time: int,
        max_processing_time: int,
        processing_time_unit: str = "days",
    ) -> Dict[str, Any]:
        """
        Create a Processing Profile (Readiness State Definition).
        """
        url = f"{self.BASE_URL}/application/shops/{shop_id}/readiness-state-definitions"
        headers = {
            "x-api-key": self.api_key,
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/x-www-form-urlencoded",
        }
        data = {
            "readiness_state": readiness_state,
            "min_processing_time": min_processing_time,
            "max_processing_time": max_processing_time,
            "processing_time_unit": processing_time_unit,
        }
        response = await self.async_client.post(url, headers=headers, data=data)
        response.raise_for_status()
        return response.json()

    async def update_processing_profile(
        self,
        shop_id: str,
        readiness_state_definition_id: str,
        readiness_state: Optional[str] = None,
        min_processing_time: Optional[int] = None,
        max_processing_time: Optional[int] = None,
        processing_time_unit: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Update a Processing Profile (Readiness State Definition).
        Only provided fields will be updated.
        """
        url = (
            f"{self.BASE_URL}/application/shops/{shop_id}/readiness-state-definitions/"
            f"{readiness_state_definition_id}"
        )
        headers = {
            "x-api-key": self.api_key,
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/x-www-form-urlencoded",
        }
        data: Dict[str, Any] = {}
        if readiness_state is not None:
            data["readiness_state"] = readiness_state
        if min_processing_time is not None:
            data["min_processing_time"] = min_processing_time
        if max_processing_time is not None:
            data["max_processing_time"] = max_processing_time
        if processing_time_unit is not None:
            data["processing_time_unit"] = processing_time_unit
        response = await self.async_client.put(url, headers=headers, data=data)
        response.raise_for_status()
        return response.json()

    async def delete_processing_profile(
        self,
        shop_id: str,
        readiness_state_definition_id: str,
    ) -> Dict[str, Any]:
        """
        Delete a Processing Profile (Readiness State Definition) by ID.
        """
        url = (
            f"{self.BASE_URL}/application/shops/{shop_id}/readiness-state-definitions/"
            f"{readiness_state_definition_id}"
        )
        response = await self.async_client.delete(url, headers=self._get_headers())
        response.raise_for_status()
        if response.text:
            return response.json()
        return {"deleted": True, "readiness_state_definition_id": readiness_state_definition_id}
    
    async def delete_listing(self, listing_id: str) -> Dict[str, Any]:
        """
        Delete a listing from a shop.
        
        Args:
            listing_id: The numeric ID of the listing to delete.
        
        Returns:
            Dictionary containing the deleted listing information.
        
        Raises:
            httpx.HTTPError: If the API request fails.
        """
        url = f"{self.BASE_URL}/application/listings/{listing_id}"
        response = await self.async_client.delete(url, headers=self._get_headers())
        response.raise_for_status()
        # DELETE typically returns the deleted resource or empty response
        if response.text:
            return response.json()
        return {"deleted": True, "listing_id": listing_id}
    
    async def close(self):
        """Close the HTTP clients."""
        self.client.close()
        await self.async_client.aclose()
    
    def __enter__(self):
        """Context manager entry."""
        return self
    
    async def __aenter__(self):
        """Async context manager entry."""
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        # For sync context manager, need to run async close
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # In async context, schedule cleanup
                asyncio.create_task(self.close())
            else:
                # In sync context, run it
                loop.run_until_complete(self.close())
        except Exception:
            # Fallback: just close sync client
            self.client.close()

