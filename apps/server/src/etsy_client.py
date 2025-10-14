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
        offset: int = 0,
        allow_suggested_title: bool = True
    ) -> Dict[str, Any]:
        """
        Get listings for a shop.
        
        Args:
            shop_id: The unique identifier for the shop.
            state: Filter by listing state. Options: 'active', 'inactive', 'draft', 
                   'expired', 'sold_out'. Default is 'active'.
            limit: Number of results to return (max 100). Default is 25.
            offset: Offset for pagination. Default is 0.
            allow_suggested_title: Include suggested titles if available. Default is True.
        
        Returns:
            Dictionary containing listings array and pagination info.
        
        Raises:
            httpx.HTTPError: If the API request fails.
        """
        url = f"{self.BASE_URL}/application/shops/{shop_id}/listings"
        params = {
            "limit": limit,
            "offset": offset,
            "allow_suggested_title": allow_suggested_title
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
        offset: int = 0,
        allow_suggested_title: bool = True
    ) -> Dict[str, Any]:
        """
        Search active listings in a shop by keywords.
        
        Args:
            shop_id: The unique identifier for the shop.
            keywords: Search term or phrase to filter listings. If not provided,
                      returns all active listings.
            limit: Number of results to return (max 100). Default is 25.
            offset: Offset for pagination. Default is 0.
            allow_suggested_title: Include suggested titles if available. Default is True.
        
        Returns:
            Dictionary containing listings array and pagination info.
        
        Raises:
            httpx.HTTPError: If the API request fails.
        """
        url = f"{self.BASE_URL}/application/shops/{shop_id}/listings/active"
        params = {
            "limit": limit,
            "offset": offset,
            "allow_suggested_title": allow_suggested_title
        }
        if keywords:
            params["keywords"] = keywords
        
        response = await self.async_client.get(url, headers=self._get_headers(), params=params)
        response.raise_for_status()
        return response.json()
    
    async def get_listing(
        self,
        listing_id: str,
        allow_suggested_title: bool = True
    ) -> Dict[str, Any]:
        """
        Get a single listing by its ID.
        
        Args:
            listing_id: The numeric ID of the listing.
            allow_suggested_title: Include suggested title if available. Default is True.
        
        Returns:
            Dictionary containing the listing information.
        
        Raises:
            httpx.HTTPError: If the API request fails.
        """
        url = f"{self.BASE_URL}/application/listings/{listing_id}"
        params = {
            "allow_suggested_title": allow_suggested_title
        }
        
        response = await self.async_client.get(url, headers=self._get_headers(), params=params)
        response.raise_for_status()
        return response.json()

    async def get_listing_inventory(
        self,
        listing_id: str,
        show_deleted: bool = False,
        includes: Optional[str] = None,
        legacy: Optional[bool] = None,
    ) -> Dict[str, Any]:
        """
        Retrieve the inventory record for a listing.

        Args:
            listing_id: The numeric ID of the listing.
            show_deleted: Whether to include deleted products/offerings.
            includes: Optional association to include (e.g., "Listing").
            legacy: Optional flag for legacy processing fields.

        Returns:
            Dictionary containing the listing inventory.

        Raises:
            httpx.HTTPError: If the API request fails.
        """
        url = f"{self.BASE_URL}/application/listings/{listing_id}/inventory"
        params: Dict[str, Any] = {}
        if show_deleted:
            params["show_deleted"] = True
        if includes:
            params["includes"] = includes
        if legacy is not None:
            params["legacy"] = bool(legacy)

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

    async def get_shipping_profiles(
        self,
        shop_id: str,
        limit: int = 25,
        offset: int = 0
    ) -> Dict[str, Any]:
        """
        Retrieve shipping profiles for a shop.
        """
        url = f"{self.BASE_URL}/application/shops/{shop_id}/shipping-profiles"
        params = {
            "limit": limit,
            "offset": offset,
        }
        response = await self.async_client.get(url, headers=self._get_headers(), params=params)
        response.raise_for_status()
        return response.json()

    async def get_shipping_profile(
        self,
        shop_id: str,
        shipping_profile_id: str,
    ) -> Dict[str, Any]:
        """
        Retrieve a single shipping profile by ID.
        """
        url = (
            f"{self.BASE_URL}/application/shops/{shop_id}/shipping-profiles/{shipping_profile_id}"
        )
        response = await self.async_client.get(url, headers=self._get_headers())
        response.raise_for_status()
        return response.json()
    
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
    
    async def get_shop_sections(self, shop_id: str) -> Dict[str, Any]:
        """
        Retrieve the list of shop sections in a specific shop.
        
        Args:
            shop_id: The unique identifier for the shop.
        
        Returns:
            Dictionary containing shop sections array.
        
        Raises:
            httpx.HTTPError: If the API request fails.
        """
        url = f"{self.BASE_URL}/application/shops/{shop_id}/sections"
        response = await self.async_client.get(url, headers=self._get_headers())
        response.raise_for_status()
        return response.json()
    
    async def get_shop_section(self, shop_id: str, shop_section_id: str) -> Dict[str, Any]:
        """
        Retrieve a single shop section by ID.
        
        Args:
            shop_id: The unique identifier for the shop.
            shop_section_id: The numeric ID of the section.
        
        Returns:
            Dictionary containing the shop section details.
        
        Raises:
            httpx.HTTPError: If the API request fails.
        """
        url = f"{self.BASE_URL}/application/shops/{shop_id}/sections/{shop_section_id}"
        response = await self.async_client.get(url, headers=self._get_headers())
        response.raise_for_status()
        return response.json()
    
    async def create_shop_section(self, shop_id: str, title: str) -> Dict[str, Any]:
        """
        Create a new section in a specific shop.
        
        Args:
            shop_id: The unique identifier for the shop.
            title: The title string for the shop section.
        
        Returns:
            Dictionary containing the created shop section.
        
        Raises:
            httpx.HTTPError: If the API request fails.
        """
        url = f"{self.BASE_URL}/application/shops/{shop_id}/sections"
        headers = {
            "x-api-key": self.api_key,
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/x-www-form-urlencoded",
        }
        data = {"title": title}
        response = await self.async_client.post(url, headers=headers, data=data)
        response.raise_for_status()
        return response.json()
    
    async def update_shop_section(
        self, 
        shop_id: str, 
        shop_section_id: str, 
        title: str
    ) -> Dict[str, Any]:
        """
        Update a section in a specific shop.
        
        Args:
            shop_id: The unique identifier for the shop.
            shop_section_id: The numeric ID of the section to update.
            title: The new title string for the shop section.
        
        Returns:
            Dictionary containing the updated shop section.
        
        Raises:
            httpx.HTTPError: If the API request fails.
        """
        url = f"{self.BASE_URL}/application/shops/{shop_id}/sections/{shop_section_id}"
        headers = {
            "x-api-key": self.api_key,
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/x-www-form-urlencoded",
        }
        data = {"title": title}
        response = await self.async_client.put(url, headers=headers, data=data)
        response.raise_for_status()
        return response.json()
    
    async def delete_shop_section(
        self, 
        shop_id: str, 
        shop_section_id: str
    ) -> Dict[str, Any]:
        """
        Delete a section in a specific shop.
        
        Args:
            shop_id: The unique identifier for the shop.
            shop_section_id: The numeric ID of the section to delete.
        
        Returns:
            Dictionary confirming the deletion.
        
        Raises:
            httpx.HTTPError: If the API request fails.
        """
        url = f"{self.BASE_URL}/application/shops/{shop_id}/sections/{shop_section_id}"
        response = await self.async_client.delete(url, headers=self._get_headers())
        response.raise_for_status()
        # DELETE typically returns empty response (204)
        if response.text:
            return response.json()
        return {"deleted": True, "shop_section_id": shop_section_id}
    
    async def get_reviews_by_listing(
        self,
        listing_id: str,
        limit: int = 25,
        offset: int = 0,
        min_created: Optional[int] = None,
        max_created: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Retrieve reviews for a specific listing.
        
        Args:
            listing_id: The numeric ID of the listing.
            limit: Number of results to return (max 100). Default is 25.
            offset: Offset for pagination. Default is 0.
            min_created: The earliest unix timestamp for when a review was created.
            max_created: The latest unix timestamp for when a review was created.
        
        Returns:
            Dictionary containing reviews array and pagination info.
        
        Raises:
            httpx.HTTPError: If the API request fails.
        """
        url = f"{self.BASE_URL}/application/listings/{listing_id}/reviews"
        params: Dict[str, Any] = {
            "limit": limit,
            "offset": offset
        }
        if min_created is not None:
            params["min_created"] = min_created
        if max_created is not None:
            params["max_created"] = max_created
        
        response = await self.async_client.get(url, headers=self._get_headers(), params=params)
        response.raise_for_status()
        return response.json()
    
    async def get_reviews_by_shop(
        self,
        shop_id: str,
        limit: int = 25,
        offset: int = 0,
        min_created: Optional[int] = None,
        max_created: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Retrieve reviews for a specific shop.
        
        Args:
            shop_id: The unique identifier for the shop.
            limit: Number of results to return (max 100). Default is 25.
            offset: Offset for pagination. Default is 0.
            min_created: The earliest unix timestamp for when a review was created.
            max_created: The latest unix timestamp for when a review was created.
        
        Returns:
            Dictionary containing reviews array and pagination info.
        
        Raises:
            httpx.HTTPError: If the API request fails.
        """
        url = f"{self.BASE_URL}/application/shops/{shop_id}/reviews"
        params: Dict[str, Any] = {
            "limit": limit,
            "offset": offset
        }
        if min_created is not None:
            params["min_created"] = min_created
        if max_created is not None:
            params["max_created"] = max_created
        
        response = await self.async_client.get(url, headers=self._get_headers(), params=params)
        response.raise_for_status()
        return response.json()
    
    # Payment & Financial Data Methods
    
    async def get_payment_ledger_entries(
        self,
        shop_id: str,
        min_created: int,
        max_created: int,
        limit: int = 25,
        offset: int = 0
    ) -> Dict[str, Any]:
        """
        Get payment account ledger entries for a shop.
        
        Args:
            shop_id: The unique identifier for the shop.
            min_created: The earliest unix timestamp for when a record was created.
            max_created: The latest unix timestamp for when a record was created.
            limit: Number of results to return (max 100). Default is 25.
            offset: Offset for pagination. Default is 0.
        
        Returns:
            Dictionary containing ledger entries array and pagination info.
        
        Raises:
            httpx.HTTPError: If the API request fails.
        """
        url = f"{self.BASE_URL}/application/shops/{shop_id}/payment-account/ledger-entries"
        params = {
            "min_created": min_created,
            "max_created": max_created,
            "limit": limit,
            "offset": offset
        }
        response = await self.async_client.get(url, headers=self._get_headers(), params=params)
        response.raise_for_status()
        return response.json()
    
    async def get_payment_by_receipt(
        self,
        shop_id: str,
        receipt_id: str
    ) -> Dict[str, Any]:
        """
        Get payment details for a specific receipt.
        
        Args:
            shop_id: The unique identifier for the shop.
            receipt_id: The numeric ID of the receipt.
        
        Returns:
            Dictionary containing payment details.
        
        Raises:
            httpx.HTTPError: If the API request fails.
        """
        url = f"{self.BASE_URL}/application/shops/{shop_id}/receipts/{receipt_id}/payments"
        response = await self.async_client.get(url, headers=self._get_headers())
        response.raise_for_status()
        return response.json()
    
    async def get_payments(
        self,
        shop_id: str,
        payment_ids: Optional[list] = None
    ) -> Dict[str, Any]:
        """
        Get shop payments, optionally filtered by payment IDs.
        
        Args:
            shop_id: The unique identifier for the shop.
            payment_ids: Optional list of payment ID integers to filter by.
        
        Returns:
            Dictionary containing payments array.
        
        Raises:
            httpx.HTTPError: If the API request fails.
        """
        url = f"{self.BASE_URL}/application/shops/{shop_id}/payments"
        params = {}
        if payment_ids:
            params["payment_ids"] = ",".join(str(id) for id in payment_ids)
        
        response = await self.async_client.get(url, headers=self._get_headers(), params=params)
        response.raise_for_status()
        return response.json()
    
    async def get_ledger_entry_payments(
        self,
        shop_id: str,
        ledger_entry_ids: list
    ) -> Dict[str, Any]:
        """
        Get payments from payment account ledger entry IDs.
        
        Args:
            shop_id: The unique identifier for the shop.
            ledger_entry_ids: List of ledger entry ID integers.
        
        Returns:
            Dictionary containing payments array.
        
        Raises:
            httpx.HTTPError: If the API request fails.
        """
        url = f"{self.BASE_URL}/application/shops/{shop_id}/payment-account/ledger-entries/payments"
        params = {
            "ledger_entry_ids": ",".join(str(id) for id in ledger_entry_ids)
        }
        response = await self.async_client.get(url, headers=self._get_headers(), params=params)
        response.raise_for_status()
        return response.json()
    
    # Shipping Profile Management Methods
    
    async def get_shipping_carriers(
        self,
        origin_country_iso: str
    ) -> Dict[str, Any]:
        """
        Get available shipping carriers for a country.
        
        Args:
            origin_country_iso: The ISO code of the country (e.g., "US", "GB").
        
        Returns:
            Dictionary containing shipping carriers and mail classes.
        
        Raises:
            httpx.HTTPError: If the API request fails.
        """
        url = f"{self.BASE_URL}/application/shipping-carriers"
        params = {"origin_country_iso": origin_country_iso}
        response = await self.async_client.get(url, headers=self._get_headers(), params=params)
        response.raise_for_status()
        return response.json()
    
    async def create_shipping_profile(
        self,
        shop_id: str,
        title: str,
        origin_country_iso: str,
        primary_cost: float,
        secondary_cost: float,
        min_processing_time: Optional[int] = None,
        max_processing_time: Optional[int] = None,
        processing_time_unit: str = "business_days",
        destination_country_iso: Optional[str] = None,
        destination_region: Optional[str] = None,
        origin_postal_code: Optional[str] = None,
        shipping_carrier_id: Optional[int] = None,
        mail_class: Optional[str] = None,
        min_delivery_days: Optional[int] = None,
        max_delivery_days: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Create a new shipping profile.
        
        Args:
            shop_id: The unique identifier for the shop.
            title: The name of the shipping profile.
            origin_country_iso: The ISO code of the country from which the listing ships.
            primary_cost: The cost of shipping to this destination alone.
            secondary_cost: The cost of shipping with another item.
            min_processing_time: Minimum processing time (1-10).
            max_processing_time: Maximum processing time (1-10).
            processing_time_unit: "business_days" or "weeks".
            destination_country_iso: ISO code of destination country (XOR with destination_region).
            destination_region: "eu", "non_eu", or "none" (XOR with destination_country_iso).
            origin_postal_code: Postal code for origin location.
            shipping_carrier_id: Carrier ID (required with mail_class if delivery days not provided).
            mail_class: Mail class (required with carrier_id if delivery days not provided).
            min_delivery_days: Minimum delivery days (required with max if carrier not provided).
            max_delivery_days: Maximum delivery days (required with min if carrier not provided).
        
        Returns:
            Dictionary containing the created shipping profile.
        
        Raises:
            httpx.HTTPError: If the API request fails.
        """
        url = f"{self.BASE_URL}/application/shops/{shop_id}/shipping-profiles"
        headers = {
            "x-api-key": self.api_key,
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/x-www-form-urlencoded",
        }
        
        data: Dict[str, Any] = {
            "title": title,
            "origin_country_iso": origin_country_iso,
            "primary_cost": primary_cost,
            "secondary_cost": secondary_cost,
            "processing_time_unit": processing_time_unit
        }
        
        if min_processing_time is not None:
            data["min_processing_time"] = min_processing_time
        if max_processing_time is not None:
            data["max_processing_time"] = max_processing_time
        if destination_country_iso is not None:
            data["destination_country_iso"] = destination_country_iso
        if destination_region is not None:
            data["destination_region"] = destination_region
        if origin_postal_code is not None:
            data["origin_postal_code"] = origin_postal_code
        if shipping_carrier_id is not None:
            data["shipping_carrier_id"] = shipping_carrier_id
        if mail_class is not None:
            data["mail_class"] = mail_class
        if min_delivery_days is not None:
            data["min_delivery_days"] = min_delivery_days
        if max_delivery_days is not None:
            data["max_delivery_days"] = max_delivery_days
        
        response = await self.async_client.post(url, headers=headers, data=data)
        response.raise_for_status()
        return response.json()
    
    async def update_shipping_profile(
        self,
        shop_id: str,
        shipping_profile_id: str,
        title: Optional[str] = None,
        origin_country_iso: Optional[str] = None,
        min_processing_time: Optional[int] = None,
        max_processing_time: Optional[int] = None,
        processing_time_unit: Optional[str] = None,
        origin_postal_code: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Update an existing shipping profile.
        
        Args:
            shop_id: The unique identifier for the shop.
            shipping_profile_id: The numeric ID of the shipping profile.
            title: The name of the shipping profile.
            origin_country_iso: The ISO code of the country from which the listing ships.
            min_processing_time: Minimum processing time (1-10).
            max_processing_time: Maximum processing time (1-10).
            processing_time_unit: "business_days" or "weeks".
            origin_postal_code: Postal code for origin location.
        
        Returns:
            Dictionary containing the updated shipping profile.
        
        Raises:
            httpx.HTTPError: If the API request fails.
        """
        url = f"{self.BASE_URL}/application/shops/{shop_id}/shipping-profiles/{shipping_profile_id}"
        headers = {
            "x-api-key": self.api_key,
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/x-www-form-urlencoded",
        }
        
        data: Dict[str, Any] = {}
        if title is not None:
            data["title"] = title
        if origin_country_iso is not None:
            data["origin_country_iso"] = origin_country_iso
        if min_processing_time is not None:
            data["min_processing_time"] = min_processing_time
        if max_processing_time is not None:
            data["max_processing_time"] = max_processing_time
        if processing_time_unit is not None:
            data["processing_time_unit"] = processing_time_unit
        if origin_postal_code is not None:
            data["origin_postal_code"] = origin_postal_code
        
        response = await self.async_client.put(url, headers=headers, data=data)
        response.raise_for_status()
        return response.json()
    
    async def delete_shipping_profile(
        self,
        shop_id: str,
        shipping_profile_id: str
    ) -> Dict[str, Any]:
        """
        Delete a shipping profile.
        
        Args:
            shop_id: The unique identifier for the shop.
            shipping_profile_id: The numeric ID of the shipping profile.
        
        Returns:
            Dictionary confirming deletion.
        
        Raises:
            httpx.HTTPError: If the API request fails.
        """
        url = f"{self.BASE_URL}/application/shops/{shop_id}/shipping-profiles/{shipping_profile_id}"
        response = await self.async_client.delete(url, headers=self._get_headers())
        response.raise_for_status()
        if response.text:
            return response.json()
        return {"deleted": True, "shipping_profile_id": shipping_profile_id}
    
    # Shipping Profile Destination Methods
    
    async def create_shipping_profile_destination(
        self,
        shop_id: str,
        shipping_profile_id: str,
        primary_cost: float,
        secondary_cost: float,
        destination_country_iso: Optional[str] = None,
        destination_region: Optional[str] = None,
        shipping_carrier_id: Optional[int] = None,
        mail_class: Optional[str] = None,
        min_delivery_days: Optional[int] = None,
        max_delivery_days: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Create a shipping destination for a shipping profile.
        
        Args:
            shop_id: The unique identifier for the shop.
            shipping_profile_id: The numeric ID of the shipping profile.
            primary_cost: The cost of shipping to this destination alone.
            secondary_cost: The cost of shipping with another item.
            destination_country_iso: ISO code of destination country (XOR with destination_region).
            destination_region: "eu", "non_eu", or "none" (XOR with destination_country_iso).
            shipping_carrier_id: Carrier ID (required with mail_class if delivery days not provided).
            mail_class: Mail class (required with carrier_id if delivery days not provided).
            min_delivery_days: Minimum delivery days (required with max if carrier not provided).
            max_delivery_days: Maximum delivery days (required with min if carrier not provided).
        
        Returns:
            Dictionary containing the created destination.
        
        Raises:
            httpx.HTTPError: If the API request fails.
        """
        url = f"{self.BASE_URL}/application/shops/{shop_id}/shipping-profiles/{shipping_profile_id}/destinations"
        headers = {
            "x-api-key": self.api_key,
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/x-www-form-urlencoded",
        }
        
        data: Dict[str, Any] = {
            "primary_cost": primary_cost,
            "secondary_cost": secondary_cost
        }
        
        if destination_country_iso is not None:
            data["destination_country_iso"] = destination_country_iso
        if destination_region is not None:
            data["destination_region"] = destination_region
        if shipping_carrier_id is not None:
            data["shipping_carrier_id"] = shipping_carrier_id
        if mail_class is not None:
            data["mail_class"] = mail_class
        if min_delivery_days is not None:
            data["min_delivery_days"] = min_delivery_days
        if max_delivery_days is not None:
            data["max_delivery_days"] = max_delivery_days
        
        response = await self.async_client.post(url, headers=headers, data=data)
        response.raise_for_status()
        return response.json()
    
    async def get_shipping_profile_destinations(
        self,
        shop_id: str,
        shipping_profile_id: str,
        limit: int = 25,
        offset: int = 0
    ) -> Dict[str, Any]:
        """
        Get shipping destinations for a shipping profile.
        
        Args:
            shop_id: The unique identifier for the shop.
            shipping_profile_id: The numeric ID of the shipping profile.
            limit: Number of results to return (max 100). Default is 25.
            offset: Offset for pagination. Default is 0.
        
        Returns:
            Dictionary containing destinations array.
        
        Raises:
            httpx.HTTPError: If the API request fails.
        """
        url = f"{self.BASE_URL}/application/shops/{shop_id}/shipping-profiles/{shipping_profile_id}/destinations"
        params = {"limit": limit, "offset": offset}
        response = await self.async_client.get(url, headers=self._get_headers(), params=params)
        response.raise_for_status()
        return response.json()
    
    async def update_shipping_profile_destination(
        self,
        shop_id: str,
        shipping_profile_id: str,
        destination_id: str,
        primary_cost: Optional[float] = None,
        secondary_cost: Optional[float] = None,
        destination_country_iso: Optional[str] = None,
        destination_region: Optional[str] = None,
        shipping_carrier_id: Optional[int] = None,
        mail_class: Optional[str] = None,
        min_delivery_days: Optional[int] = None,
        max_delivery_days: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Update a shipping destination.
        
        Args:
            shop_id: The unique identifier for the shop.
            shipping_profile_id: The numeric ID of the shipping profile.
            destination_id: The numeric ID of the destination.
            primary_cost: The cost of shipping to this destination alone.
            secondary_cost: The cost of shipping with another item.
            destination_country_iso: ISO code of destination country.
            destination_region: "eu", "non_eu", or "none".
            shipping_carrier_id: Carrier ID.
            mail_class: Mail class.
            min_delivery_days: Minimum delivery days.
            max_delivery_days: Maximum delivery days.
        
        Returns:
            Dictionary containing the updated destination.
        
        Raises:
            httpx.HTTPError: If the API request fails.
        """
        url = f"{self.BASE_URL}/application/shops/{shop_id}/shipping-profiles/{shipping_profile_id}/destinations/{destination_id}"
        headers = {
            "x-api-key": self.api_key,
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/x-www-form-urlencoded",
        }
        
        data: Dict[str, Any] = {}
        if primary_cost is not None:
            data["primary_cost"] = primary_cost
        if secondary_cost is not None:
            data["secondary_cost"] = secondary_cost
        if destination_country_iso is not None:
            data["destination_country_iso"] = destination_country_iso
        if destination_region is not None:
            data["destination_region"] = destination_region
        if shipping_carrier_id is not None:
            data["shipping_carrier_id"] = shipping_carrier_id
        if mail_class is not None:
            data["mail_class"] = mail_class
        if min_delivery_days is not None:
            data["min_delivery_days"] = min_delivery_days
        if max_delivery_days is not None:
            data["max_delivery_days"] = max_delivery_days
        
        response = await self.async_client.put(url, headers=headers, data=data)
        response.raise_for_status()
        return response.json()
    
    async def delete_shipping_profile_destination(
        self,
        shop_id: str,
        shipping_profile_id: str,
        destination_id: str
    ) -> Dict[str, Any]:
        """
        Delete a shipping destination.
        
        Args:
            shop_id: The unique identifier for the shop.
            shipping_profile_id: The numeric ID of the shipping profile.
            destination_id: The numeric ID of the destination.
        
        Returns:
            Dictionary confirming deletion.
        
        Raises:
            httpx.HTTPError: If the API request fails.
        """
        url = f"{self.BASE_URL}/application/shops/{shop_id}/shipping-profiles/{shipping_profile_id}/destinations/{destination_id}"
        response = await self.async_client.delete(url, headers=self._get_headers())
        response.raise_for_status()
        if response.text:
            return response.json()
        return {"deleted": True, "destination_id": destination_id}
    
    # Shipping Profile Upgrade Methods
    
    async def create_shipping_profile_upgrade(
        self,
        shop_id: str,
        shipping_profile_id: str,
        upgrade_type: str,
        upgrade_name: str,
        price: float,
        secondary_price: float,
        shipping_carrier_id: Optional[int] = None,
        mail_class: Optional[str] = None,
        min_delivery_days: Optional[int] = None,
        max_delivery_days: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Create a shipping upgrade for a shipping profile.
        
        Args:
            shop_id: The unique identifier for the shop.
            shipping_profile_id: The numeric ID of the shipping profile.
            upgrade_type: "0" for domestic, "1" for international.
            upgrade_name: Name of the upgrade shown to shoppers.
            price: Additional cost of the upgrade.
            secondary_price: Additional cost for each additional item.
            shipping_carrier_id: Carrier ID.
            mail_class: Mail class.
            min_delivery_days: Minimum delivery days.
            max_delivery_days: Maximum delivery days.
        
        Returns:
            Dictionary containing the created upgrade.
        
        Raises:
            httpx.HTTPError: If the API request fails.
        """
        url = f"{self.BASE_URL}/application/shops/{shop_id}/shipping-profiles/{shipping_profile_id}/upgrades"
        headers = {
            "x-api-key": self.api_key,
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/x-www-form-urlencoded",
        }
        
        data: Dict[str, Any] = {
            "type": upgrade_type,
            "upgrade_name": upgrade_name,
            "price": price,
            "secondary_price": secondary_price
        }
        
        if shipping_carrier_id is not None:
            data["shipping_carrier_id"] = shipping_carrier_id
        if mail_class is not None:
            data["mail_class"] = mail_class
        if min_delivery_days is not None:
            data["min_delivery_days"] = min_delivery_days
        if max_delivery_days is not None:
            data["max_delivery_days"] = max_delivery_days
        
        response = await self.async_client.post(url, headers=headers, data=data)
        response.raise_for_status()
        return response.json()
    
    async def get_shipping_profile_upgrades(
        self,
        shop_id: str,
        shipping_profile_id: str
    ) -> Dict[str, Any]:
        """
        Get shipping upgrades for a shipping profile.
        
        Args:
            shop_id: The unique identifier for the shop.
            shipping_profile_id: The numeric ID of the shipping profile.
        
        Returns:
            Dictionary containing upgrades array.
        
        Raises:
            httpx.HTTPError: If the API request fails.
        """
        url = f"{self.BASE_URL}/application/shops/{shop_id}/shipping-profiles/{shipping_profile_id}/upgrades"
        response = await self.async_client.get(url, headers=self._get_headers())
        response.raise_for_status()
        return response.json()
    
    async def update_shipping_profile_upgrade(
        self,
        shop_id: str,
        shipping_profile_id: str,
        upgrade_id: str,
        upgrade_name: Optional[str] = None,
        upgrade_type: Optional[str] = None,
        price: Optional[float] = None,
        secondary_price: Optional[float] = None,
        shipping_carrier_id: Optional[int] = None,
        mail_class: Optional[str] = None,
        min_delivery_days: Optional[int] = None,
        max_delivery_days: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Update a shipping upgrade.
        
        Args:
            shop_id: The unique identifier for the shop.
            shipping_profile_id: The numeric ID of the shipping profile.
            upgrade_id: The numeric ID of the upgrade.
            upgrade_name: Name of the upgrade shown to shoppers.
            upgrade_type: "0" for domestic, "1" for international.
            price: Additional cost of the upgrade.
            secondary_price: Additional cost for each additional item.
            shipping_carrier_id: Carrier ID.
            mail_class: Mail class.
            min_delivery_days: Minimum delivery days.
            max_delivery_days: Maximum delivery days.
        
        Returns:
            Dictionary containing the updated upgrade.
        
        Raises:
            httpx.HTTPError: If the API request fails.
        """
        url = f"{self.BASE_URL}/application/shops/{shop_id}/shipping-profiles/{shipping_profile_id}/upgrades/{upgrade_id}"
        headers = {
            "x-api-key": self.api_key,
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/x-www-form-urlencoded",
        }
        
        data: Dict[str, Any] = {}
        if upgrade_name is not None:
            data["upgrade_name"] = upgrade_name
        if upgrade_type is not None:
            data["type"] = upgrade_type
        if price is not None:
            data["price"] = price
        if secondary_price is not None:
            data["secondary_price"] = secondary_price
        if shipping_carrier_id is not None:
            data["shipping_carrier_id"] = shipping_carrier_id
        if mail_class is not None:
            data["mail_class"] = mail_class
        if min_delivery_days is not None:
            data["min_delivery_days"] = min_delivery_days
        if max_delivery_days is not None:
            data["max_delivery_days"] = max_delivery_days
        
        response = await self.async_client.put(url, headers=headers, data=data)
        response.raise_for_status()
        return response.json()
    
    async def delete_shipping_profile_upgrade(
        self,
        shop_id: str,
        shipping_profile_id: str,
        upgrade_id: str
    ) -> Dict[str, Any]:
        """
        Delete a shipping upgrade.
        
        Args:
            shop_id: The unique identifier for the shop.
            shipping_profile_id: The numeric ID of the shipping profile.
            upgrade_id: The numeric ID of the upgrade.
        
        Returns:
            Dictionary confirming deletion.
        
        Raises:
            httpx.HTTPError: If the API request fails.
        """
        url = f"{self.BASE_URL}/application/shops/{shop_id}/shipping-profiles/{shipping_profile_id}/upgrades/{upgrade_id}"
        response = await self.async_client.delete(url, headers=self._get_headers())
        response.raise_for_status()
        if response.text:
            return response.json()
        return {"deleted": True, "upgrade_id": upgrade_id}
    
    # Return Policy Methods
    
    async def get_return_policies(
        self,
        shop_id: str
    ) -> Dict[str, Any]:
        """
        Get all return policies for a shop.
        
        Args:
            shop_id: The unique identifier for the shop.
        
        Returns:
            Dictionary containing return policies array.
        
        Raises:
            httpx.HTTPError: If the API request fails.
        """
        url = f"{self.BASE_URL}/application/shops/{shop_id}/policies/return"
        response = await self.async_client.get(url, headers=self._get_headers())
        response.raise_for_status()
        return response.json()
    
    async def get_return_policy(
        self,
        shop_id: str,
        return_policy_id: str
    ) -> Dict[str, Any]:
        """
        Get a single return policy by ID.
        
        Args:
            shop_id: The unique identifier for the shop.
            return_policy_id: The numeric ID of the return policy.
        
        Returns:
            Dictionary containing return policy details.
        
        Raises:
            httpx.HTTPError: If the API request fails.
        """
        url = f"{self.BASE_URL}/application/shops/{shop_id}/policies/return/{return_policy_id}"
        response = await self.async_client.get(url, headers=self._get_headers())
        response.raise_for_status()
        return response.json()
    
    async def create_return_policy(
        self,
        shop_id: str,
        accepts_returns: bool,
        accepts_exchanges: bool,
        return_deadline: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Create a new return policy.
        
        Args:
            shop_id: The unique identifier for the shop.
            accepts_returns: Whether the shop accepts returns.
            accepts_exchanges: Whether the shop accepts exchanges.
            return_deadline: Days for return deadline (7, 14, 21, 30, 45, 60, 90).
                             Required if either accepts flag is true.
        
        Returns:
            Dictionary containing the created return policy.
        
        Raises:
            httpx.HTTPError: If the API request fails.
        """
        url = f"{self.BASE_URL}/application/shops/{shop_id}/policies/return"
        headers = {
            "x-api-key": self.api_key,
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/x-www-form-urlencoded",
        }
        
        data: Dict[str, Any] = {
            "accepts_returns": accepts_returns,
            "accepts_exchanges": accepts_exchanges
        }
        
        if return_deadline is not None:
            data["return_deadline"] = return_deadline
        
        response = await self.async_client.post(url, headers=headers, data=data)
        response.raise_for_status()
        return response.json()
    
    async def update_return_policy(
        self,
        shop_id: str,
        return_policy_id: str,
        accepts_returns: bool,
        accepts_exchanges: bool,
        return_deadline: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Update an existing return policy.
        
        Args:
            shop_id: The unique identifier for the shop.
            return_policy_id: The numeric ID of the return policy.
            accepts_returns: Whether the shop accepts returns.
            accepts_exchanges: Whether the shop accepts exchanges.
            return_deadline: Days for return deadline (7, 14, 21, 30, 45, 60, 90).
                             Required if either accepts flag is true.
        
        Returns:
            Dictionary containing the updated return policy.
        
        Raises:
            httpx.HTTPError: If the API request fails.
        """
        url = f"{self.BASE_URL}/application/shops/{shop_id}/policies/return/{return_policy_id}"
        headers = {
            "x-api-key": self.api_key,
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/x-www-form-urlencoded",
        }
        
        data: Dict[str, Any] = {
            "accepts_returns": accepts_returns,
            "accepts_exchanges": accepts_exchanges
        }
        
        if return_deadline is not None:
            data["return_deadline"] = return_deadline
        
        response = await self.async_client.put(url, headers=headers, data=data)
        response.raise_for_status()
        return response.json()
    
    async def delete_return_policy(
        self,
        shop_id: str,
        return_policy_id: str
    ) -> Dict[str, Any]:
        """
        Delete a return policy.
        
        Args:
            shop_id: The unique identifier for the shop.
            return_policy_id: The numeric ID of the return policy.
        
        Returns:
            Dictionary confirming deletion.
        
        Raises:
            httpx.HTTPError: If the API request fails.
        """
        url = f"{self.BASE_URL}/application/shops/{shop_id}/policies/return/{return_policy_id}"
        response = await self.async_client.delete(url, headers=self._get_headers())
        response.raise_for_status()
        if response.text:
            return response.json()
        return {"deleted": True, "return_policy_id": return_policy_id}
    
    async def consolidate_return_policies(
        self,
        shop_id: str,
        source_return_policy_id: str,
        destination_return_policy_id: str
    ) -> Dict[str, Any]:
        """
        Consolidate return policies by moving listings from source to destination.
        
        Args:
            shop_id: The unique identifier for the shop.
            source_return_policy_id: The numeric ID of the source return policy.
            destination_return_policy_id: The numeric ID of the destination return policy.
        
        Returns:
            Dictionary containing the updated destination return policy.
        
        Raises:
            httpx.HTTPError: If the API request fails.
        """
        url = f"{self.BASE_URL}/application/shops/{shop_id}/policies/return/consolidate"
        headers = {
            "x-api-key": self.api_key,
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/x-www-form-urlencoded",
        }
        
        data = {
            "source_return_policy_id": source_return_policy_id,
            "destination_return_policy_id": destination_return_policy_id
        }
        
        response = await self.async_client.post(url, headers=headers, data=data)
        response.raise_for_status()
        return response.json()
    
    # Shop Update Methods
    
    async def update_shop(
        self,
        shop_id: str,
        title: Optional[str] = None,
        announcement: Optional[str] = None,
        sale_message: Optional[str] = None,
        digital_sale_message: Optional[str] = None,
        policy_additional: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Update shop information.
        
        Args:
            shop_id: The unique identifier for the shop.
            title: Shop title/heading.
            announcement: Shop announcement displayed on homepage.
            sale_message: Message sent to buyers who complete a purchase.
            digital_sale_message: Message sent to buyers who purchase digital items.
            policy_additional: Additional shop policies (EU shops only).
        
        Returns:
            Dictionary containing the updated shop information.
        
        Raises:
            httpx.HTTPError: If the API request fails.
        """
        url = f"{self.BASE_URL}/application/shops/{shop_id}"
        headers = {
            "x-api-key": self.api_key,
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/x-www-form-urlencoded",
        }
        
        data: Dict[str, Any] = {}
        if title is not None:
            data["title"] = title
        if announcement is not None:
            data["announcement"] = announcement
        if sale_message is not None:
            data["sale_message"] = sale_message
        if digital_sale_message is not None:
            data["digital_sale_message"] = digital_sale_message
        if policy_additional is not None:
            data["policy_additional"] = policy_additional
        
        response = await self.async_client.put(url, headers=headers, data=data)
        response.raise_for_status()
        return response.json()
    
    async def get_holiday_preferences(
        self,
        shop_id: str
    ) -> Dict[str, Any]:
        """
        Get shop holiday preferences.
        
        Args:
            shop_id: The unique identifier for the shop.
        
        Returns:
            Dictionary containing holiday preferences array.
        
        Raises:
            httpx.HTTPError: If the API request fails.
        """
        url = f"{self.BASE_URL}/application/shops/{shop_id}/holiday-preferences"
        response = await self.async_client.get(url, headers=self._get_headers())
        response.raise_for_status()
        return response.json()
    
    async def update_holiday_preference(
        self,
        shop_id: str,
        holiday_id: str,
        is_working: bool
    ) -> Dict[str, Any]:
        """
        Update a holiday preference for the shop.
        
        Args:
            shop_id: The unique identifier for the shop.
            holiday_id: The numeric ID of the holiday.
            is_working: Whether the shop will process orders on this holiday.
        
        Returns:
            Dictionary containing the updated holiday preference.
        
        Raises:
            httpx.HTTPError: If the API request fails.
        """
        url = f"{self.BASE_URL}/application/shops/{shop_id}/holiday-preferences/{holiday_id}"
        headers = {
            "x-api-key": self.api_key,
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/x-www-form-urlencoded",
        }
        
        data = {"is_working": is_working}
        
        response = await self.async_client.put(url, headers=headers, data=data)
        response.raise_for_status()
        return response.json()
    
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

