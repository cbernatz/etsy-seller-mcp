"""Etsy Seller MCP Server - Main entry point."""

import os
import sys
from pathlib import Path
import webbrowser
import keyring
import json
from datetime import datetime
from typing import Optional, Dict, Any

# Add the src directory to the path so imports work
sys.path.insert(0, str(Path(__file__).parent))

from dotenv import load_dotenv
from fastmcp import FastMCP
from etsy_client import EtsyClient
from oauth_manager import OAuthManager
from callback_server import OAuthCallbackServer

# Load environment variables from .env file
load_dotenv()

# Initialize FastMCP server
mcp = FastMCP("Etsy Seller MCP")

# Initialize OAuth manager
oauth_manager = None
try:
    oauth_manager = OAuthManager()
except ValueError as e:
    print(f"Warning: OAuth manager not initialized: {e}")
    print("You'll need to set ETSY_API_KEY to use connect_etsy tool.")

# Session-based token storage (persisted via keyring)
session_token = None
etsy_client = None

# Keyring service name for storing tokens
KEYRING_SERVICE = "etsy-seller-mcp"
KEYRING_TOKEN_KEY = "access_token"
KEYRING_METADATA_KEY = "token_metadata"


def save_token_to_keyring(access_token: str, expires_at: str) -> None:
    """
    Save OAuth token to system keyring.
    
    Args:
        access_token: The OAuth access token
        expires_at: ISO format timestamp for token expiration
    """
    try:
        # Store the access token
        keyring.set_password(KEYRING_SERVICE, KEYRING_TOKEN_KEY, access_token)
        
        # Store metadata (expiration time)
        metadata = json.dumps({"expires_at": expires_at})
        keyring.set_password(KEYRING_SERVICE, KEYRING_METADATA_KEY, metadata)
        
        print(f"✓ Token saved to system keyring")
    except Exception as e:
        print(f"Warning: Could not save token to keyring: {e}")


def load_token_from_keyring() -> Optional[Dict[str, Any]]:
    """
    Load OAuth token from system keyring.
    
    Returns:
        Dictionary with access_token and expires_at, or None if not found/expired
    """
    try:
        # Load access token
        access_token = keyring.get_password(KEYRING_SERVICE, KEYRING_TOKEN_KEY)
        if not access_token:
            return None
        
        # Load metadata
        metadata_json = keyring.get_password(KEYRING_SERVICE, KEYRING_METADATA_KEY)
        if not metadata_json:
            return None
        
        metadata = json.loads(metadata_json)
        expires_at = metadata.get("expires_at")
        
        # Check if token is expired
        if expires_at:
            expiry = datetime.fromisoformat(expires_at)
            if datetime.utcnow() >= expiry:
                print("Stored token has expired. Please reconnect.")
                delete_token_from_keyring()
                return None
        
        return {
            "access_token": access_token,
            "expires_at": expires_at
        }
    except Exception as e:
        print(f"Warning: Could not load token from keyring: {e}")
        return None


def delete_token_from_keyring() -> None:
    """Delete OAuth token from system keyring."""
    try:
        keyring.delete_password(KEYRING_SERVICE, KEYRING_TOKEN_KEY)
        keyring.delete_password(KEYRING_SERVICE, KEYRING_METADATA_KEY)
        print("✓ Token deleted from system keyring")
    except keyring.errors.PasswordDeleteError:
        # Token doesn't exist, that's fine
        pass
    except Exception as e:
        print(f"Warning: Could not delete token from keyring: {e}")


def restore_session_from_keyring() -> bool:
    """
    Restore session from keyring on server startup.
    
    Returns:
        True if session was restored, False otherwise
    """
    global session_token, etsy_client
    
    token_data = load_token_from_keyring()
    if token_data:
        session_token = token_data["access_token"]
        etsy_client = EtsyClient(access_token=session_token)
        print(f"\n{'='*60}")
        print("SESSION RESTORED FROM KEYRING")
        print(f"{'='*60}")
        print(f"Token expires: {token_data['expires_at']}")
        print("You're already connected to Etsy!")
        print(f"{'='*60}\n")
        return True
    return False


# Try to restore session on startup
restore_session_from_keyring()


@mcp.tool()
async def connect_etsy() -> dict:
    """
    Connect your Etsy account via OAuth 2.0. This will open a browser window for authorization.
    The token will be securely stored in your system's keyring and automatically restored on restart.
    
    Returns:
        Dictionary with connection status and instructions
    """
    global session_token, etsy_client
    
    if not oauth_manager:
        return {
            "success": False,
            "error": "OAuth manager not initialized. Please set ETSY_API_KEY environment variable."
        }
    
    try:
        # Request comprehensive shop management scopes
        scopes = [
            "shops_r",           # Read shop info
            "shops_w",           # Write shop info
            "listings_r",        # Read listings
            "listings_w",        # Write listings  
            "listings_d",        # Delete listings
            "transactions_r",    # Read transactions
            "profile_r",         # Read profile
            "email_r",           # Read email
            "address_r",         # Read addresses
            "address_w",         # Write addresses
        ]
        
        # Generate authorization URL
        auth_data = oauth_manager.get_authorization_url(scopes)
        
        # Start callback server
        callback_server = OAuthCallbackServer()
        callback_server.start()
        
        print(f"\n{'='*60}")
        print("ETSY AUTHORIZATION REQUIRED")
        print(f"{'='*60}")
        print("\nOpening browser for authorization...")
        print(f"If browser doesn't open, visit this URL:\n{auth_data['url']}\n")
        
        # Open browser
        webbrowser.open(auth_data['url'])
        
        print("Waiting for authorization (timeout: 5 minutes)...")
        
        # Wait for callback
        try:
            callback_data = callback_server.wait_for_callback(timeout=300)
        finally:
            callback_server.stop()
        
        # Check for errors
        if callback_data.get("error"):
            return {
                "success": False,
                "error": f"Authorization failed: {callback_data['error']}"
            }
        
        code = callback_data.get("code")
        state = callback_data.get("state")
        
        if not code:
            return {
                "success": False,
                "error": "No authorization code received"
            }
        
        # Verify state
        if state != auth_data["state"]:
            return {
                "success": False,
                "error": "State mismatch - possible CSRF attack"
            }
        
        # Exchange code for token
        print("Exchanging authorization code for access token...")
        token_data = await oauth_manager.exchange_code_for_token(
            code, 
            auth_data["code_verifier"]
        )
        
        # Store token in memory for this session
        session_token = token_data["access_token"]
        
        # Save token to system keyring for persistence
        save_token_to_keyring(session_token, token_data["expires_at"])
        
        # Initialize Etsy client with the access token
        etsy_client = EtsyClient(access_token=session_token)
        
        print(f"\n{'='*60}")
        print("AUTHORIZATION SUCCESSFUL!")
        print(f"{'='*60}\n")
        print("Token securely stored in system keyring.")
        print("It will be automatically restored when you restart the server.\n")
        
        return {
            "success": True,
            "message": "Successfully connected to Etsy! Token stored securely in system keyring.",
            "expires_at": token_data["expires_at"]
        }
    
    except TimeoutError:
        return {
            "success": False,
            "error": "Authorization timed out. Please try again."
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"Authorization failed: {str(e)}"
        }


@mcp.tool()
async def disconnect_etsy() -> dict:
    """
    Disconnect the current Etsy session by clearing the token from memory and system keyring.
    
    Returns:
        Dictionary with disconnection status
    """
    global session_token, etsy_client
    
    if session_token is None and etsy_client is None:
        return {
            "success": False,
            "error": "No active Etsy connection to disconnect."
        }
    
    # Clear session data
    session_token = None
    etsy_client = None
    
    # Delete token from system keyring
    delete_token_from_keyring()
    
    return {
        "success": True,
        "message": "Successfully disconnected from Etsy. Token cleared from memory and keyring."
    }


@mcp.tool()
async def get_connection_status() -> dict:
    """
    Check if there's an active Etsy connection in this session.
    
    Returns:
        Dictionary containing connection status
    """
    return {
        "success": True,
        "connected": etsy_client is not None,
        "message": "Connected to Etsy" if etsy_client else "Not connected. Use connect_etsy to authenticate."
    }


@mcp.tool()
async def get_my_shop() -> dict:
    """
    Get detailed information about the authenticated user's Etsy shop.
    
    This tool automatically extracts the user_id from the OAuth token and 
    retrieves the user's shop information without needing to know the shop ID.
    
    Returns:
        Dictionary containing shop details including:
        - shop_id: Unique shop identifier
        - shop_name: Shop name
        - title: Shop title
        - announcement: Shop announcement
        - currency_code: Shop currency
        - is_vacation: Whether shop is on vacation
        - url: Shop URL
        - user_id: The authenticated user's ID
        - and more...
    """
    if etsy_client is None:
        return {
            "success": False,
            "error": "Not connected to Etsy. Please use connect_etsy tool first."
        }
    
    try:
        # Get current user info (includes user_id and shop_id)
        user_data = await etsy_client.get_current_user()
        user_id = user_data.get("user_id")
        shop_id = user_data.get("shop_id")
        
        if not shop_id:
            return {
                "success": False,
                "error": "No shop_id found for this user. You may need to create an Etsy shop first."
            }
        
        # Get detailed shop information
        shop_data = await etsy_client.get_shop(str(shop_id))
        
        # Return shop details with user_id
        return {
            "success": True,
            "shop": shop_data,
            "user_id": user_id
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"Error retrieving shop information: {str(e)}"
        }


@mcp.tool()
async def get_my_listings(
    keywords: str = None,
    state: str = "active",
    limit: int = 25,
    offset: int = 0,
    allow_suggested_title: bool = True
) -> dict:
    """
    Get or search listings from your Etsy shop. This comprehensive tool handles all 
    listing retrieval scenarios - filtering by state, searching by keywords, or both.
    
    Args:
        keywords: Optional search term or phrase to filter listings (e.g., "handmade", 
                  "blue scarf"). When provided with state='active', uses keyword search.
                  Cannot be used with non-active states.
        state: Filter by listing state. Options: 'active', 'inactive', 'draft', 
               'expired', 'sold_out'. Default is 'active'.
        limit: Number of results to return (1-100). Default is 25.
        offset: Offset for pagination. Default is 0.
        allow_suggested_title: Include suggested titles if available (English shops only). 
                                Default is True.
    
    Returns:
        Dictionary containing:
        - count: Total number of listings matching the criteria
        - results: Array of listing objects with details like:
          - listing_id: Unique listing identifier
          - title: Listing title
          - suggested_title: Suggested title (if available and enabled)
          - description: Listing description
          - price: Listing price
          - quantity: Available quantity
          - state: Current state (active, draft, etc.)
          - url: Listing URL
          - tags: Array of tags
          - and more...
        - filters_applied: Summary of filters used
    
    Examples:
        - Get all active listings: get_my_listings()
        - Search active listings: get_my_listings(keywords="handmade")
        - Get draft listings: get_my_listings(state="draft")
        - Get inactive listings: get_my_listings(state="inactive")
    """
    if etsy_client is None:
        return {
            "success": False,
            "error": "Not connected to Etsy. Please use connect_etsy tool first."
        }
    
    # Validate that keywords are only used with active state
    if keywords and state != "active":
        return {
            "success": False,
            "error": f"Keyword search is only available for active listings. You specified state='{state}'. "
                     f"Either remove keywords parameter or set state='active'."
        }
    
    try:
        # Get current user info to extract shop_id
        user_data = await etsy_client.get_current_user()
        shop_id = user_data.get("shop_id")
        
        if not shop_id:
            return {
                "success": False,
                "error": "No shop_id found for this user."
            }
        
        # Validate limit
        if limit < 1 or limit > 100:
            return {
                "success": False,
                "error": "Limit must be between 1 and 100."
            }
        
        # Choose the right endpoint based on parameters
        if keywords:
            # Use keyword search endpoint (active listings only)
            listings_data = await etsy_client.search_shop_listings(
                str(shop_id), 
                keywords=keywords,
                limit=limit,
                offset=offset,
                allow_suggested_title=allow_suggested_title
            )
            filters_applied = {
                "state": "active",
                "keywords": keywords,
                "limit": limit,
                "offset": offset,
                "allow_suggested_title": allow_suggested_title
            }
        else:
            # Use general listings endpoint (supports all states)
            listings_data = await etsy_client.get_shop_listings(
                str(shop_id), 
                state=state,
                limit=limit,
                offset=offset,
                allow_suggested_title=allow_suggested_title
            )
            filters_applied = {
                "state": state,
                "keywords": None,
                "limit": limit,
                "offset": offset,
                "allow_suggested_title": allow_suggested_title
            }
        
        return {
            "success": True,
            "count": listings_data.get("count", 0),
            "results": listings_data.get("results", []),
            "filters_applied": filters_applied
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"Error retrieving listings: {str(e)}"
        }


@mcp.tool()
async def get_listing(
    listing_id: int,
    allow_suggested_title: bool = True
) -> dict:
    """
    Get detailed information about a single listing by its ID.
    
    Args:
        listing_id: The unique identifier of the listing
        allow_suggested_title: Include suggested title if available (English shops only). 
                                Default is True.
    
    Returns:
        Dictionary containing:
        - success: Whether the request was successful
        - listing: Listing object with details including:
          - listing_id: Unique listing identifier
          - title: Listing title
          - suggested_title: Suggested title (if available and enabled)
          - description: Listing description
          - price: Listing price
          - quantity: Available quantity
          - state: Current state (active, draft, etc.)
          - url: Listing URL
          - tags: Array of tags
          - and more...
    
    Example:
        - Get listing details: get_listing(listing_id=123456789)
    """
    if etsy_client is None:
        return {
            "success": False,
            "error": "Not connected to Etsy. Please use connect_etsy tool first."
        }
    
    try:
        # Get the listing
        listing_data = await etsy_client.get_listing(
            str(listing_id),
            allow_suggested_title=allow_suggested_title
        )
        
        return {
            "success": True,
            "listing": listing_data
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"Error retrieving listing: {str(e)}"
        }


@mcp.tool()
async def update_my_listing(
    listing_id: int,
    state: str = None,
    title: str = None,
    description: str = None,
    price: float = None,
    quantity: int = None,
    tags: list = None,
    shop_section_id: int = None
) -> dict:
    """
    Update a listing in your Etsy shop. You can update various properties including
    the listing state (to activate, deactivate, or set to draft) and assign it to a shop section.
    
    Args:
        listing_id: The unique identifier of the listing to update
        state: Listing state. Options: 'active', 'inactive', 'draft'
        title: New listing title
        description: New listing description
        price: New price (in dollars, e.g., 5.50 for $5.50)
        quantity: New quantity available
        tags: List of tags for the listing
        shop_section_id: ID of the shop section to assign this listing to
    
    Returns:
        Dictionary containing:
        - success: Whether the update was successful
        - message: Confirmation message
        - listing: Updated listing information
    """
    if etsy_client is None:
        return {
            "success": False,
            "error": "Not connected to Etsy. Please use connect_etsy tool first."
        }
    
    try:
        # Get current user info to extract shop_id
        user_data = await etsy_client.get_current_user()
        shop_id = user_data.get("shop_id")
        
        if not shop_id:
            return {
                "success": False,
                "error": "No shop_id found for this user."
            }
        
        # Build update parameters
        update_params = {}
        
        if state is not None:
            # Validate state
            valid_states = ['active', 'inactive', 'draft']
            if state not in valid_states:
                return {
                    "success": False,
                    "error": f"Invalid state '{state}'. Must be one of: {', '.join(valid_states)}"
                }
            update_params['state'] = state
        
        if title is not None:
            update_params['title'] = title
        
        if description is not None:
            update_params['description'] = description
        
        if price is not None:
            # Convert price to Etsy's format (amount in cents)
            update_params['price'] = price
        
        if quantity is not None:
            update_params['quantity'] = quantity
        
        if tags is not None:
            update_params['tags'] = tags
        
        if shop_section_id is not None:
            update_params['shop_section_id'] = shop_section_id
        
        if not update_params:
            return {
                "success": False,
                "error": "No update parameters provided. Please specify at least one property to update."
            }
        
        # Update the listing
        result = await etsy_client.update_listing(str(shop_id), str(listing_id), **update_params)
        
        return {
            "success": True,
            "message": f"Successfully updated listing {listing_id}",
            "listing": result
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"Error updating listing: {str(e)}"
        }


@mcp.tool()
async def get_processing_profiles(limit: int = 25, offset: int = 0) -> dict:
    """
    List Processing Profiles (readiness state definitions) for your shop.
    """
    if etsy_client is None:
        return {
            "success": False,
            "error": "Not connected to Etsy. Please use connect_etsy tool first."
        }
    try:
        user_data = await etsy_client.get_current_user()
        shop_id = user_data.get("shop_id")
        if not shop_id:
            return {"success": False, "error": "No shop_id found for this user."}
        profiles = await etsy_client.get_processing_profiles(str(shop_id), limit=limit, offset=offset)
        return {"success": True, "results": profiles.get("results", []), "count": profiles.get("count", 0)}
    except Exception as e:
        return {"success": False, "error": f"Error listing processing profiles: {str(e)}"}


@mcp.tool()
async def get_processing_profile(readiness_state_definition_id: int) -> dict:
    """
    Get a single Processing Profile by its ID.
    """
    if etsy_client is None:
        return {
            "success": False,
            "error": "Not connected to Etsy. Please use connect_etsy tool first."
        }
    try:
        user_data = await etsy_client.get_current_user()
        shop_id = user_data.get("shop_id")
        if not shop_id:
            return {"success": False, "error": "No shop_id found for this user."}
        profile = await etsy_client.get_processing_profile(str(shop_id), str(readiness_state_definition_id))
        return {"success": True, "profile": profile}
    except Exception as e:
        return {"success": False, "error": f"Error getting processing profile: {str(e)}"}


@mcp.tool()
async def create_processing_profile(
    readiness_state: str,
    min_processing_time: int,
    max_processing_time: int,
    processing_time_unit: str = "days"
) -> dict:
    """
    Create a Processing Profile for your shop.
    readiness_state: "ready_to_ship" or "made_to_order"
    processing_time_unit: "days" or "weeks"
    """
    if etsy_client is None:
        return {
            "success": False,
            "error": "Not connected to Etsy. Please use connect_etsy tool first."
        }
    try:
        user_data = await etsy_client.get_current_user()
        shop_id = user_data.get("shop_id")
        if not shop_id:
            return {"success": False, "error": "No shop_id found for this user."}
        profile = await etsy_client.create_processing_profile(
            str(shop_id),
            readiness_state=readiness_state,
            min_processing_time=min_processing_time,
            max_processing_time=max_processing_time,
            processing_time_unit=processing_time_unit,
        )
        return {"success": True, "profile": profile}
    except Exception as e:
        return {"success": False, "error": f"Error creating processing profile: {str(e)}"}


@mcp.tool()
async def update_processing_profile(
    readiness_state_definition_id: int,
    readiness_state: str = None,
    min_processing_time: int = None,
    max_processing_time: int = None,
    processing_time_unit: str = None
) -> dict:
    """
    Update fields on a Processing Profile.
    Only provided parameters are updated.
    """
    if etsy_client is None:
        return {
            "success": False,
            "error": "Not connected to Etsy. Please use connect_etsy tool first."
        }
    try:
        user_data = await etsy_client.get_current_user()
        shop_id = user_data.get("shop_id")
        if not shop_id:
            return {"success": False, "error": "No shop_id found for this user."}
        profile = await etsy_client.update_processing_profile(
            str(shop_id),
            str(readiness_state_definition_id),
            readiness_state=readiness_state,
            min_processing_time=min_processing_time,
            max_processing_time=max_processing_time,
            processing_time_unit=processing_time_unit,
        )
        return {"success": True, "profile": profile}
    except Exception as e:
        return {"success": False, "error": f"Error updating processing profile: {str(e)}"}


@mcp.tool()
async def delete_processing_profile(readiness_state_definition_id: int) -> dict:
    """
    Delete a Processing Profile by ID.
    """
    if etsy_client is None:
        return {
            "success": False,
            "error": "Not connected to Etsy. Please use connect_etsy tool first."
        }
    try:
        user_data = await etsy_client.get_current_user()
        shop_id = user_data.get("shop_id")
        if not shop_id:
            return {"success": False, "error": "No shop_id found for this user."}
        result = await etsy_client.delete_processing_profile(str(shop_id), str(readiness_state_definition_id))
        return {"success": True, "deleted": True, "result": result}
    except Exception as e:
        return {"success": False, "error": f"Error deleting processing profile: {str(e)}"}


@mcp.tool()
async def assign_processing_profile_to_listing(
    listing_id: int,
    readiness_state_definition_id: int
) -> dict:
    """
    Assign a Processing Profile to a listing by updating its readiness_state_id.
    """
    if etsy_client is None:
        return {
            "success": False,
            "error": "Not connected to Etsy. Please use connect_etsy tool first."
        }
    try:
        user_data = await etsy_client.get_current_user()
        shop_id = user_data.get("shop_id")
        if not shop_id:
            return {"success": False, "error": "No shop_id found for this user."}
        updated = await etsy_client.update_listing(
            str(shop_id),
            str(listing_id),
            legacy=True,
            readiness_state_id=int(readiness_state_definition_id),
        )
        return {"success": True, "listing": updated}
    except Exception as e:
        return {"success": False, "error": f"Error assigning processing profile to listing: {str(e)}"}


@mcp.tool()
async def get_shipping_profiles(limit: int = 25, offset: int = 0) -> dict:
    """
    List Shipping Profiles for your shop.
    """
    if etsy_client is None:
        return {
            "success": False,
            "error": "Not connected to Etsy. Please use connect_etsy tool first."
        }
    try:
        user_data = await etsy_client.get_current_user()
        shop_id = user_data.get("shop_id")
        if not shop_id:
            return {"success": False, "error": "No shop_id found for this user."}
        profiles = await etsy_client.get_shipping_profiles(str(shop_id), limit=limit, offset=offset)
        return {"success": True, "results": profiles.get("results", []), "count": profiles.get("count", 0)}
    except Exception as e:
        return {"success": False, "error": f"Error listing shipping profiles: {str(e)}"}


@mcp.tool()
async def get_shipping_profile(shipping_profile_id: int) -> dict:
    """
    Get a single Shipping Profile by ID.
    """
    if etsy_client is None:
        return {
            "success": False,
            "error": "Not connected to Etsy. Please use connect_etsy tool first."
        }
    try:
        user_data = await etsy_client.get_current_user()
        shop_id = user_data.get("shop_id")
        if not shop_id:
            return {"success": False, "error": "No shop_id found for this user."}
        profile = await etsy_client.get_shipping_profile(str(shop_id), str(shipping_profile_id))
        return {"success": True, "profile": profile}
    except Exception as e:
        return {"success": False, "error": f"Error getting shipping profile: {str(e)}"}

@mcp.tool()
async def delete_my_listing(listing_id: int) -> dict:
    """
    Delete a listing from your Etsy shop.
    
    WARNING: This action is permanent and cannot be undone!
    
    Args:
        listing_id: The unique identifier of the listing to delete
    
    Returns:
        Dictionary containing:
        - success: Whether the deletion was successful
        - message: Confirmation message with the deleted listing_id
        - deleted_listing: Information about the deleted listing (if available)
    """
    if etsy_client is None:
        return {
            "success": False,
            "error": "Not connected to Etsy. Please use connect_etsy tool first."
        }
    
    try:
        # Delete the listing
        result = await etsy_client.delete_listing(str(listing_id))
        
        return {
            "success": True,
            "message": f"Successfully deleted listing {listing_id}",
            "deleted_listing": result
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"Error deleting listing: {str(e)}"
        }


@mcp.tool()
async def get_shop_sections() -> dict:
    """
    Get all shop sections from your Etsy shop.
    
    Shop sections organize listings displayed in an Etsy shop. Each section has a 
    title and can contain multiple listings.
    
    Returns:
        Dictionary containing:
        - success: Whether the request was successful
        - count: Number of sections
        - results: Array of section objects with details like:
          - shop_section_id: Unique section identifier
          - title: Section title
          - rank: Display order
          - active_listing_count: Number of active listings in the section
    
    Example:
        - Get all sections: get_shop_sections()
    """
    if etsy_client is None:
        return {
            "success": False,
            "error": "Not connected to Etsy. Please use connect_etsy tool first."
        }
    
    try:
        user_data = await etsy_client.get_current_user()
        shop_id = user_data.get("shop_id")
        
        if not shop_id:
            return {
                "success": False,
                "error": "No shop_id found for this user."
            }
        
        sections_data = await etsy_client.get_shop_sections(str(shop_id))
        
        return {
            "success": True,
            "count": sections_data.get("count", 0),
            "results": sections_data.get("results", [])
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"Error retrieving shop sections: {str(e)}"
        }


@mcp.tool()
async def get_shop_section(shop_section_id: int) -> dict:
    """
    Get a single shop section by its ID.
    
    Args:
        shop_section_id: The numeric ID of the section
    
    Returns:
        Dictionary containing:
        - success: Whether the request was successful
        - section: Section object with details including:
          - shop_section_id: Unique section identifier
          - title: Section title
          - rank: Display order
          - active_listing_count: Number of active listings in the section
    
    Example:
        - Get section details: get_shop_section(shop_section_id=12345)
    """
    if etsy_client is None:
        return {
            "success": False,
            "error": "Not connected to Etsy. Please use connect_etsy tool first."
        }
    
    try:
        user_data = await etsy_client.get_current_user()
        shop_id = user_data.get("shop_id")
        
        if not shop_id:
            return {
                "success": False,
                "error": "No shop_id found for this user."
            }
        
        section_data = await etsy_client.get_shop_section(str(shop_id), str(shop_section_id))
        
        return {
            "success": True,
            "section": section_data
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"Error retrieving shop section: {str(e)}"
        }


@mcp.tool()
async def create_shop_section(title: str) -> dict:
    """
    Create a new section in your Etsy shop.
    
    Shop sections organize listings displayed in an Etsy shop. After creating a section,
    you can assign listings to it using the update_my_listing tool with the shop_section_id parameter.
    
    Args:
        title: The title string for the new shop section
    
    Returns:
        Dictionary containing:
        - success: Whether the creation was successful
        - message: Confirmation message
        - section: Created section object with:
          - shop_section_id: Unique section identifier (use this to assign listings)
          - title: Section title
          - rank: Display order
          - active_listing_count: Number of active listings (will be 0 for new sections)
    
    Example:
        - Create a section: create_shop_section(title="Handmade Pottery")
    """
    if etsy_client is None:
        return {
            "success": False,
            "error": "Not connected to Etsy. Please use connect_etsy tool first."
        }
    
    try:
        user_data = await etsy_client.get_current_user()
        shop_id = user_data.get("shop_id")
        
        if not shop_id:
            return {
                "success": False,
                "error": "No shop_id found for this user."
            }
        
        section_data = await etsy_client.create_shop_section(str(shop_id), title)
        
        return {
            "success": True,
            "message": f"Successfully created shop section '{title}'",
            "section": section_data
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"Error creating shop section: {str(e)}"
        }


@mcp.tool()
async def update_shop_section(shop_section_id: int, title: str) -> dict:
    """
    Update a section in your Etsy shop.
    
    Args:
        shop_section_id: The numeric ID of the section to update
        title: The new title string for the shop section
    
    Returns:
        Dictionary containing:
        - success: Whether the update was successful
        - message: Confirmation message
        - section: Updated section object with:
          - shop_section_id: Unique section identifier
          - title: Updated section title
          - rank: Display order
          - active_listing_count: Number of active listings in the section
    
    Example:
        - Update a section: update_shop_section(shop_section_id=12345, title="Ceramic Art")
    """
    if etsy_client is None:
        return {
            "success": False,
            "error": "Not connected to Etsy. Please use connect_etsy tool first."
        }
    
    try:
        user_data = await etsy_client.get_current_user()
        shop_id = user_data.get("shop_id")
        
        if not shop_id:
            return {
                "success": False,
                "error": "No shop_id found for this user."
            }
        
        section_data = await etsy_client.update_shop_section(
            str(shop_id), 
            str(shop_section_id), 
            title
        )
        
        return {
            "success": True,
            "message": f"Successfully updated shop section {shop_section_id}",
            "section": section_data
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"Error updating shop section: {str(e)}"
        }


@mcp.tool()
async def delete_shop_section(shop_section_id: int) -> dict:
    """
    Delete a section from your Etsy shop.
    
    This will delete the section but will NOT delete the listings in that section.
    Listings will simply no longer be organized in that section.
    
    Args:
        shop_section_id: The numeric ID of the section to delete
    
    Returns:
        Dictionary containing:
        - success: Whether the deletion was successful
        - message: Confirmation message
        - shop_section_id: ID of the deleted section
    
    Example:
        - Delete a section: delete_shop_section(shop_section_id=12345)
    """
    if etsy_client is None:
        return {
            "success": False,
            "error": "Not connected to Etsy. Please use connect_etsy tool first."
        }
    
    try:
        user_data = await etsy_client.get_current_user()
        shop_id = user_data.get("shop_id")
        
        if not shop_id:
            return {
                "success": False,
                "error": "No shop_id found for this user."
            }
        
        result = await etsy_client.delete_shop_section(str(shop_id), str(shop_section_id))
        
        return {
            "success": True,
            "message": f"Successfully deleted shop section {shop_section_id}",
            "shop_section_id": shop_section_id
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"Error deleting shop section: {str(e)}"
        }


if __name__ == "__main__":
    # Run the MCP server
    mcp.run()

