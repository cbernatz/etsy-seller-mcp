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

    async def update_listing_property(
        self,
        shop_id: str,
        listing_id: str,
        property_id: int,
        value_ids: list,
        values: list,
        scale_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Update or populate a listing property (e.g., color, occasion, holiday).
        
        Args:
            shop_id: The unique identifier for the shop.
            listing_id: The numeric ID of the listing to update.
            property_id: The unique ID of the property (e.g., 200 for Primary Color).
            value_ids: Array of value IDs for the property.
            values: Array of value strings for the property.
            scale_id: Optional scale ID for properties that have scales.
        
        Returns:
            Dictionary containing the updated listing property information.
        
        Raises:
            httpx.HTTPError: If the API request fails.
        """
        url = f"{self.BASE_URL}/application/shops/{shop_id}/listings/{listing_id}/properties/{property_id}"
        
        # Build form data
        data = {
            "value_ids": value_ids,
            "values": values
        }
        
        if scale_id is not None:
            data["scale_id"] = scale_id
        
        # updateListingProperty expects application/x-www-form-urlencoded format
        headers = {
            "x-api-key": self.api_key,
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/x-www-form-urlencoded",
        }
        
        response = await self.async_client.put(url, headers=headers, data=data)
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
    
    # Receipt Management Methods
    
    async def get_shop_receipts(
        self,
        shop_id: str,
        limit: int = 25,
        offset: int = 0,
        min_created: Optional[int] = None,
        max_created: Optional[int] = None,
        min_last_modified: Optional[int] = None,
        max_last_modified: Optional[int] = None,
        was_paid: Optional[bool] = None,
        was_shipped: Optional[bool] = None,
        was_delivered: Optional[bool] = None,
        was_canceled: Optional[bool] = None,
        sort_on: str = "created",
        sort_order: str = "desc"
    ) -> Dict[str, Any]:
        """
        Get shop receipts with optional filters.
        
        Args:
            shop_id: The unique identifier for the shop.
            limit: Number of results to return (max 100). Default is 25.
            offset: Offset for pagination. Default is 0.
            min_created: The earliest unix timestamp for when a record was created.
            max_created: The latest unix timestamp for when a record was created.
            min_last_modified: The earliest unix timestamp for when a record last changed.
            max_last_modified: The latest unix timestamp for when a record last changed.
            was_paid: Filter by payment status.
            was_shipped: Filter by shipment status.
            was_delivered: Filter by delivery status.
            was_canceled: Filter by cancellation status.
            sort_on: Sort by field. Options: 'created', 'updated', 'receipt_id'.
            sort_order: Sort order. Options: 'asc', 'desc'.
        
        Returns:
            Dictionary containing receipts array and pagination info.
        
        Raises:
            httpx.HTTPError: If the API request fails.
        """
        url = f"{self.BASE_URL}/application/shops/{shop_id}/receipts"
        params: Dict[str, Any] = {
            "limit": limit,
            "offset": offset,
            "sort_on": sort_on,
            "sort_order": sort_order
        }
        
        if min_created is not None:
            params["min_created"] = min_created
        if max_created is not None:
            params["max_created"] = max_created
        if min_last_modified is not None:
            params["min_last_modified"] = min_last_modified
        if max_last_modified is not None:
            params["max_last_modified"] = max_last_modified
        if was_paid is not None:
            params["was_paid"] = was_paid
        if was_shipped is not None:
            params["was_shipped"] = was_shipped
        if was_delivered is not None:
            params["was_delivered"] = was_delivered
        if was_canceled is not None:
            params["was_canceled"] = was_canceled
        
        response = await self.async_client.get(url, headers=self._get_headers(), params=params)
        response.raise_for_status()
        return response.json()
    
    async def get_shop_receipt(
        self,
        shop_id: str,
        receipt_id: str
    ) -> Dict[str, Any]:
        """
        Get a single shop receipt by ID.
        
        Args:
            shop_id: The unique identifier for the shop.
            receipt_id: The numeric ID of the receipt.
        
        Returns:
            Dictionary containing receipt details.
        
        Raises:
            httpx.HTTPError: If the API request fails.
        """
        url = f"{self.BASE_URL}/application/shops/{shop_id}/receipts/{receipt_id}"
        response = await self.async_client.get(url, headers=self._get_headers())
        response.raise_for_status()
        return response.json()
    
    async def update_shop_receipt(
        self,
        shop_id: str,
        receipt_id: str,
        was_shipped: Optional[bool] = None,
        was_paid: Optional[bool] = None
    ) -> Dict[str, Any]:
        """
        Update a shop receipt.
        
        Args:
            shop_id: The unique identifier for the shop.
            receipt_id: The numeric ID of the receipt.
            was_shipped: Whether the receipt has been shipped.
            was_paid: Whether the receipt has been paid.
        
        Returns:
            Dictionary containing the updated receipt.
        
        Raises:
            httpx.HTTPError: If the API request fails.
        """
        url = f"{self.BASE_URL}/application/shops/{shop_id}/receipts/{receipt_id}"
        headers = {
            "x-api-key": self.api_key,
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/x-www-form-urlencoded",
        }
        
        data: Dict[str, Any] = {}
        if was_shipped is not None:
            data["was_shipped"] = was_shipped
        if was_paid is not None:
            data["was_paid"] = was_paid
        
        response = await self.async_client.put(url, headers=headers, data=data)
        response.raise_for_status()
        return response.json()
    
    async def create_receipt_shipment(
        self,
        shop_id: str,
        receipt_id: str,
        tracking_code: Optional[str] = None,
        carrier_name: Optional[str] = None,
        send_bcc: bool = False,
        note_to_buyer: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Submit tracking information for a shop receipt.
        
        Args:
            shop_id: The unique identifier for the shop.
            receipt_id: The numeric ID of the receipt.
            tracking_code: The tracking code for this receipt.
            carrier_name: The carrier name for this receipt.
            send_bcc: If true, shipping notification sent to seller as well.
            note_to_buyer: Message to include in notification to the buyer.
        
        Returns:
            Dictionary containing the updated receipt with shipment info.
        
        Raises:
            httpx.HTTPError: If the API request fails.
        """
        url = f"{self.BASE_URL}/application/shops/{shop_id}/receipts/{receipt_id}/tracking"
        headers = {
            "x-api-key": self.api_key,
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/x-www-form-urlencoded",
        }
        
        data: Dict[str, Any] = {}
        if tracking_code is not None:
            data["tracking_code"] = tracking_code
        if carrier_name is not None:
            data["carrier_name"] = carrier_name
        if send_bcc:
            data["send_bcc"] = send_bcc
        if note_to_buyer is not None:
            data["note_to_buyer"] = note_to_buyer
        
        response = await self.async_client.post(url, headers=headers, data=data)
        response.raise_for_status()
        return response.json()
    
    # Transaction Methods
    
    async def get_shop_transactions(
        self,
        shop_id: str,
        limit: int = 25,
        offset: int = 0
    ) -> Dict[str, Any]:
        """
        Get all transactions for a shop.
        
        Args:
            shop_id: The unique identifier for the shop.
            limit: Number of results to return (max 100). Default is 25.
            offset: Offset for pagination. Default is 0.
        
        Returns:
            Dictionary containing transactions array and pagination info.
        
        Raises:
            httpx.HTTPError: If the API request fails.
        """
        url = f"{self.BASE_URL}/application/shops/{shop_id}/transactions"
        params = {
            "limit": limit,
            "offset": offset
        }
        response = await self.async_client.get(url, headers=self._get_headers(), params=params)
        response.raise_for_status()
        return response.json()
    
    async def get_receipt_transactions(
        self,
        shop_id: str,
        receipt_id: str
    ) -> Dict[str, Any]:
        """
        Get transactions for a specific receipt.
        
        Args:
            shop_id: The unique identifier for the shop.
            receipt_id: The numeric ID of the receipt.
        
        Returns:
            Dictionary containing transactions array.
        
        Raises:
            httpx.HTTPError: If the API request fails.
        """
        url = f"{self.BASE_URL}/application/shops/{shop_id}/receipts/{receipt_id}/transactions"
        response = await self.async_client.get(url, headers=self._get_headers())
        response.raise_for_status()
        return response.json()
    
    async def get_listing_transactions(
        self,
        shop_id: str,
        listing_id: str,
        limit: int = 25,
        offset: int = 0
    ) -> Dict[str, Any]:
        """
        Get transactions for a specific listing.
        
        Args:
            shop_id: The unique identifier for the shop.
            listing_id: The numeric ID of the listing.
            limit: Number of results to return (max 100). Default is 25.
            offset: Offset for pagination. Default is 0.
        
        Returns:
            Dictionary containing transactions array and pagination info.
        
        Raises:
            httpx.HTTPError: If the API request fails.
        """
        url = f"{self.BASE_URL}/application/shops/{shop_id}/listings/{listing_id}/transactions"
        params = {
            "limit": limit,
            "offset": offset
        }
        response = await self.async_client.get(url, headers=self._get_headers(), params=params)
        response.raise_for_status()
        return response.json()
    
    # Listing Creation Methods
    
    async def create_draft_listing(
        self,
        shop_id: str,
        quantity: int,
        title: str,
        description: str,
        price: float,
        who_made: str,
        when_made: str,
        taxonomy_id: int,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Create a draft listing.
        
        Args:
            shop_id: The unique identifier for the shop.
            quantity: Positive non-zero number of products available.
            title: The listing's title string.
            description: Description of the product for sale.
            price: Positive non-zero price of the product.
            who_made: Who made the product. Options: 'i_did', 'someone_else', 'collective'.
            when_made: When the product was made. Options: 'made_to_order', '2020_2025', etc.
            taxonomy_id: The numerical taxonomy ID of the listing.
            **kwargs: Optional parameters like shipping_profile_id, return_policy_id, tags, 
                     materials, is_supply, type, shop_section_id, etc.
        
        Returns:
            Dictionary containing the created listing.
        
        Raises:
            httpx.HTTPError: If the API request fails.
        """
        url = f"{self.BASE_URL}/application/shops/{shop_id}/listings"
        headers = {
            "x-api-key": self.api_key,
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/x-www-form-urlencoded",
        }
        
        data: Dict[str, Any] = {
            "quantity": quantity,
            "title": title,
            "description": description,
            "price": price,
            "who_made": who_made,
            "when_made": when_made,
            "taxonomy_id": taxonomy_id
        }
        
        # Add optional parameters
        for key, value in kwargs.items():
            if value is not None:
                data[key] = value
        
        response = await self.async_client.post(url, headers=headers, data=data)
        response.raise_for_status()
        return response.json()
    
    # Listing Image Methods
    
    async def get_listing_images(
        self,
        listing_id: str
    ) -> Dict[str, Any]:
        """
        Get all images for a listing.
        
        Args:
            listing_id: The numeric ID of the listing.
        
        Returns:
            Dictionary containing images array.
        
        Raises:
            httpx.HTTPError: If the API request fails.
        """
        url = f"{self.BASE_URL}/application/listings/{listing_id}/images"
        response = await self.async_client.get(url, headers=self._get_headers())
        response.raise_for_status()
        return response.json()
    
    async def upload_listing_image(
        self,
        shop_id: str,
        listing_id: str,
        image_path: str,
        rank: Optional[int] = None,
        overwrite: bool = False,
        is_watermarked: bool = False,
        alt_text: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Upload a new image to a listing.
        
        Args:
            shop_id: The unique identifier for the shop.
            listing_id: The numeric ID of the listing.
            image_path: Path to the image file to upload.
            rank: Position in the images displayed (1 is leftmost).
            overwrite: When true, replaces existing image at given rank.
            is_watermarked: When true, indicates the image has a watermark.
            alt_text: Alt text for the image (max 500 characters).
        
        Returns:
            Dictionary containing the uploaded image details.
        
        Raises:
            httpx.HTTPError: If the API request fails.
        """
        import mimetypes
        from pathlib import Path
        
        url = f"{self.BASE_URL}/application/shops/{shop_id}/listings/{listing_id}/images"
        headers = {
            "x-api-key": self.api_key,
            "Authorization": f"Bearer {self.access_token}",
        }
        
        # Read image file
        image_file = Path(image_path)
        mime_type = mimetypes.guess_type(image_path)[0] or "image/jpeg"
        
        with open(image_file, "rb") as f:
            image_data = f.read()
        
        # Prepare multipart form data
        files = {"image": (image_file.name, image_data, mime_type)}
        data: Dict[str, Any] = {}
        
        if rank is not None:
            data["rank"] = rank
        if overwrite:
            data["overwrite"] = overwrite
        if is_watermarked:
            data["is_watermarked"] = is_watermarked
        if alt_text is not None:
            data["alt_text"] = alt_text
        
        response = await self.async_client.post(url, headers=headers, files=files, data=data)
        response.raise_for_status()
        return response.json()
    
    async def delete_listing_image(
        self,
        shop_id: str,
        listing_id: str,
        listing_image_id: str
    ) -> Dict[str, Any]:
        """
        Delete an image from a listing.
        
        Args:
            shop_id: The unique identifier for the shop.
            listing_id: The numeric ID of the listing.
            listing_image_id: The numeric ID of the image to delete.
        
        Returns:
            Dictionary confirming deletion.
        
        Raises:
            httpx.HTTPError: If the API request fails.
        """
        url = f"{self.BASE_URL}/application/shops/{shop_id}/listings/{listing_id}/images/{listing_image_id}"
        response = await self.async_client.delete(url, headers=self._get_headers())
        response.raise_for_status()
        if response.text:
            return response.json()
        return {"deleted": True, "listing_image_id": listing_image_id}
    
    async def update_variation_images(
        self,
        shop_id: str,
        listing_id: str,
        variation_images: list
    ) -> Dict[str, Any]:
        """
        Update variation images for a listing.
        
        Args:
            shop_id: The unique identifier for the shop.
            listing_id: The numeric ID of the listing.
            variation_images: Array of objects with property_id, value_id, and image_id.
        
        Returns:
            Dictionary containing the updated variation images.
        
        Raises:
            httpx.HTTPError: If the API request fails.
        """
        url = f"{self.BASE_URL}/application/shops/{shop_id}/listings/{listing_id}/variation-images"
        headers = {
            "x-api-key": self.api_key,
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
        }
        
        payload = {"variation_images": variation_images}
        
        response = await self.async_client.post(url, headers=headers, json=payload)
        response.raise_for_status()
        return response.json()
    
    # Inventory Update Methods
    
    async def update_listing_inventory(
        self,
        listing_id: str,
        products: list,
        price_on_property: Optional[list] = None,
        quantity_on_property: Optional[list] = None,
        sku_on_property: Optional[list] = None,
        readiness_state_on_property: Optional[list] = None
    ) -> Dict[str, Any]:
        """
        Update the inventory for a listing.
        
        Args:
            listing_id: The numeric ID of the listing.
            products: Array of product objects with offerings.
            price_on_property: Array of property IDs that affect pricing.
            quantity_on_property: Array of property IDs that affect quantity.
            sku_on_property: Array of property IDs that affect SKU.
            readiness_state_on_property: Array of property IDs that affect processing.
        
        Returns:
            Dictionary containing the updated inventory.
        
        Raises:
            httpx.HTTPError: If the API request fails.
        """
        url = f"{self.BASE_URL}/application/listings/{listing_id}/inventory"
        headers = {
            "x-api-key": self.api_key,
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
        }
        
        payload: Dict[str, Any] = {"products": products}
        
        if price_on_property is not None:
            payload["price_on_property"] = price_on_property
        if quantity_on_property is not None:
            payload["quantity_on_property"] = quantity_on_property
        if sku_on_property is not None:
            payload["sku_on_property"] = sku_on_property
        if readiness_state_on_property is not None:
            payload["readiness_state_on_property"] = readiness_state_on_property
        
        response = await self.async_client.put(url, headers=headers, json=payload)
        response.raise_for_status()
        return response.json()
    
    # Listing File Methods (Digital Products)
    
    async def get_listing_files(
        self,
        listing_id: str
    ) -> Dict[str, Any]:
        """
        Get all files for a listing.
        
        Args:
            listing_id: The numeric ID of the listing.
        
        Returns:
            Dictionary containing files array.
        
        Raises:
            httpx.HTTPError: If the API request fails.
        """
        url = f"{self.BASE_URL}/application/listings/{listing_id}/files"
        response = await self.async_client.get(url, headers=self._get_headers())
        response.raise_for_status()
        return response.json()
    
    async def get_listing_file(
        self,
        shop_id: str,
        listing_id: str,
        listing_file_id: str
    ) -> Dict[str, Any]:
        """
        Get a single file for a listing.
        
        Args:
            shop_id: The unique identifier for the shop.
            listing_id: The numeric ID of the listing.
            listing_file_id: The numeric ID of the file.
        
        Returns:
            Dictionary containing file metadata.
        
        Raises:
            httpx.HTTPError: If the API request fails.
        """
        url = f"{self.BASE_URL}/application/shops/{shop_id}/listings/{listing_id}/files/{listing_file_id}"
        response = await self.async_client.get(url, headers=self._get_headers())
        response.raise_for_status()
        return response.json()
    
    async def upload_listing_file(
        self,
        shop_id: str,
        listing_id: str,
        file_path: str,
        name: Optional[str] = None,
        rank: int = 1
    ) -> Dict[str, Any]:
        """
        Upload a file to a digital listing.
        
        Args:
            shop_id: The unique identifier for the shop.
            listing_id: The numeric ID of the listing.
            file_path: Path to the file to upload.
            name: Optional name for the file.
            rank: Position in file display (default: 1).
        
        Returns:
            Dictionary containing the uploaded file metadata.
        
        Raises:
            httpx.HTTPError: If the API request fails.
        """
        import mimetypes
        from pathlib import Path
        
        url = f"{self.BASE_URL}/application/shops/{shop_id}/listings/{listing_id}/files"
        headers = {
            "x-api-key": self.api_key,
            "Authorization": f"Bearer {self.access_token}",
        }
        
        file_obj = Path(file_path)
        mime_type = mimetypes.guess_type(file_path)[0] or "application/octet-stream"
        
        with open(file_obj, "rb") as f:
            file_data = f.read()
        
        files = {"file": (file_obj.name, file_data, mime_type)}
        data: Dict[str, Any] = {"rank": rank}
        
        if name is not None:
            data["name"] = name
        
        response = await self.async_client.post(url, headers=headers, files=files, data=data)
        response.raise_for_status()
        return response.json()
    
    async def delete_listing_file(
        self,
        shop_id: str,
        listing_id: str,
        listing_file_id: str
    ) -> Dict[str, Any]:
        """
        Delete a file from a listing.
        
        Args:
            shop_id: The unique identifier for the shop.
            listing_id: The numeric ID of the listing.
            listing_file_id: The numeric ID of the file.
        
        Returns:
            Dictionary confirming deletion.
        
        Raises:
            httpx.HTTPError: If the API request fails.
        """
        url = f"{self.BASE_URL}/application/shops/{shop_id}/listings/{listing_id}/files/{listing_file_id}"
        response = await self.async_client.delete(url, headers=self._get_headers())
        response.raise_for_status()
        if response.text:
            return response.json()
        return {"deleted": True, "listing_file_id": listing_file_id}
    
    # Listing Video Methods
    
    async def get_listing_videos(
        self,
        listing_id: str
    ) -> Dict[str, Any]:
        """
        Get all videos for a listing.
        
        Args:
            listing_id: The numeric ID of the listing.
        
        Returns:
            Dictionary containing videos array.
        
        Raises:
            httpx.HTTPError: If the API request fails.
        """
        url = f"{self.BASE_URL}/application/listings/{listing_id}/videos"
        response = await self.async_client.get(url, headers=self._get_headers())
        response.raise_for_status()
        return response.json()
    
    async def get_listing_video(
        self,
        listing_id: str,
        video_id: str
    ) -> Dict[str, Any]:
        """
        Get a single video for a listing.
        
        Args:
            listing_id: The numeric ID of the listing.
            video_id: The numeric ID of the video.
        
        Returns:
            Dictionary containing video metadata.
        
        Raises:
            httpx.HTTPError: If the API request fails.
        """
        url = f"{self.BASE_URL}/application/listings/{listing_id}/videos/{video_id}"
        response = await self.async_client.get(url, headers=self._get_headers())
        response.raise_for_status()
        return response.json()
    
    async def upload_listing_video(
        self,
        shop_id: str,
        listing_id: str,
        video_path: str,
        name: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Upload a video to a listing.
        
        Args:
            shop_id: The unique identifier for the shop.
            listing_id: The numeric ID of the listing.
            video_path: Path to the video file to upload.
            name: Optional name for the video.
        
        Returns:
            Dictionary containing the uploaded video metadata.
        
        Raises:
            httpx.HTTPError: If the API request fails.
        """
        import mimetypes
        from pathlib import Path
        
        url = f"{self.BASE_URL}/application/shops/{shop_id}/listings/{listing_id}/videos"
        headers = {
            "x-api-key": self.api_key,
            "Authorization": f"Bearer {self.access_token}",
        }
        
        video_obj = Path(video_path)
        mime_type = mimetypes.guess_type(video_path)[0] or "video/mp4"
        
        with open(video_obj, "rb") as f:
            video_data = f.read()
        
        files = {"video": (video_obj.name, video_data, mime_type)}
        data: Dict[str, Any] = {}
        
        if name is not None:
            data["name"] = name
        
        response = await self.async_client.post(url, headers=headers, files=files, data=data)
        response.raise_for_status()
        return response.json()
    
    async def delete_listing_video(
        self,
        shop_id: str,
        listing_id: str,
        video_id: str
    ) -> Dict[str, Any]:
        """
        Delete a video from a listing.
        
        Args:
            shop_id: The unique identifier for the shop.
            listing_id: The numeric ID of the listing.
            video_id: The numeric ID of the video.
        
        Returns:
            Dictionary confirming deletion.
        
        Raises:
            httpx.HTTPError: If the API request fails.
        """
        url = f"{self.BASE_URL}/application/shops/{shop_id}/listings/{listing_id}/videos/{video_id}"
        response = await self.async_client.delete(url, headers=self._get_headers())
        response.raise_for_status()
        if response.text:
            return response.json()
        return {"deleted": True, "video_id": video_id}
    
    # Listing Translation Methods
    
    async def create_listing_translation(
        self,
        shop_id: str,
        listing_id: str,
        language: str,
        title: str,
        description: str,
        tags: Optional[list] = None
    ) -> Dict[str, Any]:
        """
        Create a listing translation.
        
        Args:
            shop_id: The unique identifier for the shop.
            listing_id: The numeric ID of the listing.
            language: IETF language tag (e.g., 'de', 'es', 'fr').
            title: Translated title.
            description: Translated description.
            tags: Optional array of translated tags.
        
        Returns:
            Dictionary containing the created translation.
        
        Raises:
            httpx.HTTPError: If the API request fails.
        """
        url = f"{self.BASE_URL}/application/shops/{shop_id}/listings/{listing_id}/translations/{language}"
        headers = {
            "x-api-key": self.api_key,
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/x-www-form-urlencoded",
        }
        
        data: Dict[str, Any] = {
            "title": title,
            "description": description
        }
        
        if tags is not None:
            data["tags"] = tags
        
        response = await self.async_client.post(url, headers=headers, data=data)
        response.raise_for_status()
        return response.json()
    
    async def get_listing_translation(
        self,
        shop_id: str,
        listing_id: str,
        language: str
    ) -> Dict[str, Any]:
        """
        Get a listing translation.
        
        Args:
            shop_id: The unique identifier for the shop.
            listing_id: The numeric ID of the listing.
            language: IETF language tag (e.g., 'de', 'es', 'fr').
        
        Returns:
            Dictionary containing the translation.
        
        Raises:
            httpx.HTTPError: If the API request fails.
        """
        url = f"{self.BASE_URL}/application/shops/{shop_id}/listings/{listing_id}/translations/{language}"
        response = await self.async_client.get(url, headers=self._get_headers())
        response.raise_for_status()
        return response.json()
    
    async def update_listing_translation(
        self,
        shop_id: str,
        listing_id: str,
        language: str,
        title: str,
        description: str,
        tags: Optional[list] = None
    ) -> Dict[str, Any]:
        """
        Update a listing translation.
        
        Args:
            shop_id: The unique identifier for the shop.
            listing_id: The numeric ID of the listing.
            language: IETF language tag (e.g., 'de', 'es', 'fr').
            title: Translated title.
            description: Translated description.
            tags: Optional array of translated tags.
        
        Returns:
            Dictionary containing the updated translation.
        
        Raises:
            httpx.HTTPError: If the API request fails.
        """
        url = f"{self.BASE_URL}/application/shops/{shop_id}/listings/{listing_id}/translations/{language}"
        headers = {
            "x-api-key": self.api_key,
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/x-www-form-urlencoded",
        }
        
        data: Dict[str, Any] = {
            "title": title,
            "description": description
        }
        
        if tags is not None:
            data["tags"] = tags
        
        response = await self.async_client.put(url, headers=headers, data=data)
        response.raise_for_status()
        return response.json()
    
    # Taxonomy Methods
    
    async def get_buyer_taxonomy(self) -> Dict[str, Any]:
        """
        Get the full buyer taxonomy tree.
        
        Returns:
            Dictionary containing buyer taxonomy nodes.
        
        Raises:
            httpx.HTTPError: If the API request fails.
        """
        url = f"{self.BASE_URL}/application/buyer-taxonomy/nodes"
        response = await self.async_client.get(url, headers=self._get_headers())
        response.raise_for_status()
        return response.json()
    
    async def get_buyer_taxonomy_properties(
        self,
        taxonomy_id: str
    ) -> Dict[str, Any]:
        """
        Get properties for a buyer taxonomy node.
        
        Args:
            taxonomy_id: The numeric taxonomy ID.
        
        Returns:
            Dictionary containing properties and values.
        
        Raises:
            httpx.HTTPError: If the API request fails.
        """
        url = f"{self.BASE_URL}/application/buyer-taxonomy/nodes/{taxonomy_id}/properties"
        response = await self.async_client.get(url, headers=self._get_headers())
        response.raise_for_status()
        return response.json()
    
    async def get_seller_taxonomy(self) -> Dict[str, Any]:
        """
        Get the full seller taxonomy tree.
        
        Returns:
            Dictionary containing seller taxonomy nodes.
        
        Raises:
            httpx.HTTPError: If the API request fails.
        """
        url = f"{self.BASE_URL}/application/seller-taxonomy/nodes"
        response = await self.async_client.get(url, headers=self._get_headers())
        response.raise_for_status()
        return response.json()
    
    async def get_seller_taxonomy_properties(
        self,
        taxonomy_id: str
    ) -> Dict[str, Any]:
        """
        Get properties for a seller taxonomy node.
        
        Args:
            taxonomy_id: The numeric taxonomy ID.
        
        Returns:
            Dictionary containing properties and values.
        
        Raises:
            httpx.HTTPError: If the API request fails.
        """
        url = f"{self.BASE_URL}/application/seller-taxonomy/nodes/{taxonomy_id}/properties"
        response = await self.async_client.get(url, headers=self._get_headers())
        response.raise_for_status()
        return response.json()
    
    # Featured Listings Methods
    
    async def get_featured_listings(
        self,
        shop_id: str,
        limit: int = 25,
        offset: int = 0
    ) -> Dict[str, Any]:
        """
        Get featured listings for a shop.
        
        Args:
            shop_id: The unique identifier for the shop.
            limit: Number of results to return (max 100). Default is 25.
            offset: Offset for pagination. Default is 0.
        
        Returns:
            Dictionary containing featured listings array.
        
        Raises:
            httpx.HTTPError: If the API request fails.
        """
        url = f"{self.BASE_URL}/application/shops/{shop_id}/listings/featured"
        params = {
            "limit": limit,
            "offset": offset
        }
        response = await self.async_client.get(url, headers=self._get_headers(), params=params)
        response.raise_for_status()
        return response.json()
    
    # Production Partners Methods
    
    async def get_production_partners(
        self,
        shop_id: str
    ) -> Dict[str, Any]:
        """
        Get production partners for a shop.
        
        Args:
            shop_id: The unique identifier for the shop.
        
        Returns:
            Dictionary containing production partners array.
        
        Raises:
            httpx.HTTPError: If the API request fails.
        """
        url = f"{self.BASE_URL}/application/shops/{shop_id}/production-partners"
        response = await self.async_client.get(url, headers=self._get_headers())
        response.raise_for_status()
        return response.json()
    
    # User Address Methods
    
    async def get_user_addresses(
        self,
        limit: int = 25,
        offset: int = 0
    ) -> Dict[str, Any]:
        """
        Get all user addresses.
        
        Args:
            limit: Number of results to return (max 100). Default is 25.
            offset: Offset for pagination. Default is 0.
        
        Returns:
            Dictionary containing addresses array.
        
        Raises:
            httpx.HTTPError: If the API request fails.
        """
        url = f"{self.BASE_URL}/application/user/addresses"
        params = {
            "limit": limit,
            "offset": offset
        }
        response = await self.async_client.get(url, headers=self._get_headers(), params=params)
        response.raise_for_status()
        return response.json()
    
    async def get_user_address(
        self,
        user_address_id: str
    ) -> Dict[str, Any]:
        """
        Get a single user address.
        
        Args:
            user_address_id: The numeric ID of the address.
        
        Returns:
            Dictionary containing address details.
        
        Raises:
            httpx.HTTPError: If the API request fails.
        """
        url = f"{self.BASE_URL}/application/user/addresses/{user_address_id}"
        response = await self.async_client.get(url, headers=self._get_headers())
        response.raise_for_status()
        return response.json()
    
    async def delete_user_address(
        self,
        user_address_id: str
    ) -> Dict[str, Any]:
        """
        Delete a user address.
        
        Args:
            user_address_id: The numeric ID of the address.
        
        Returns:
            Dictionary confirming deletion.
        
        Raises:
            httpx.HTTPError: If the API request fails.
        """
        url = f"{self.BASE_URL}/application/user/addresses/{user_address_id}"
        response = await self.async_client.delete(url, headers=self._get_headers())
        response.raise_for_status()
        if response.text:
            return response.json()
        return {"deleted": True, "user_address_id": user_address_id}
    
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

