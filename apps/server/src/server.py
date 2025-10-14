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
async def auth(action: str) -> dict:
    """
    Consolidated authentication tool.
    
    Args:
        action: One of 'connect', 'disconnect', 'status'
    
    Returns:
        Result dictionary matching the specific action.
    """
    normalized = (action or "").strip().lower()
    if normalized not in {"connect", "disconnect", "status"}:
        return {"success": False, "error": "Invalid action. Use one of: connect, disconnect, status."}

    if normalized == "status":
        return await get_connection_status()
    if normalized == "connect":
        return await connect_etsy()
    # normalized == "disconnect"
    return await disconnect_etsy()


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
async def get_listing_inventory(
    listing_id: int,
    show_deleted: bool = False
) -> dict:
    """
    Get the full inventory matrix for a listing (products, offerings, property values).
    
    Args:
        listing_id: The unique identifier of the listing.
        show_deleted: Include deleted products/offerings.
    
    Returns:
        Dictionary containing:
        - success: Whether the request was successful
        - inventory: Raw inventory payload from Etsy (products, offerings, *_on_property fields)
    """
    if etsy_client is None:
        return {
            "success": False,
            "error": "Not connected to Etsy. Please use connect_etsy tool first."
        }
    
    try:
        inventory = await etsy_client.get_listing_inventory(
            str(listing_id),
            show_deleted=bool(show_deleted)
        )
        return {
            "success": True,
            "inventory": inventory
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"Error retrieving listing inventory: {str(e)}"
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


@mcp.tool()
async def get_reviews_by_listing(
    listing_id: int,
    limit: int = 25,
    offset: int = 0,
    min_created: int = None,
    max_created: int = None
) -> dict:
    """
    Get reviews for a specific listing.
    
    Reviews provide valuable feedback from buyers about their purchase experience.
    This endpoint retrieves transaction reviews associated with a particular listing.
    
    Args:
        listing_id: The numeric ID of the listing
        limit: Number of results to return (1-100). Default is 25.
        offset: Offset for pagination. Default is 0.
        min_created: The earliest unix timestamp for when a review was created (optional)
        max_created: The latest unix timestamp for when a review was created (optional)
    
    Returns:
        Dictionary containing:
        - success: Whether the request was successful
        - count: Total number of reviews
        - results: Array of review objects with details like:
          - rating: Review rating
          - review: Review text
          - language: Language code
          - buyer_user_id: ID of the buyer who left the review
          - create_timestamp: When the review was created
          - created_timestamp: When the review was created
          - update_timestamp: When the review was last updated
          - updated_timestamp: When the review was last updated
    
    Example:
        - Get all reviews: get_reviews_by_listing(listing_id=123456789)
        - Get recent reviews: get_reviews_by_listing(listing_id=123456789, min_created=1609459200)
    """
    if etsy_client is None:
        return {
            "success": False,
            "error": "Not connected to Etsy. Please use connect_etsy tool first."
        }
    
    try:
        # Validate limit
        if limit < 1 or limit > 100:
            return {
                "success": False,
                "error": "Limit must be between 1 and 100."
            }
        
        reviews_data = await etsy_client.get_reviews_by_listing(
            str(listing_id),
            limit=limit,
            offset=offset,
            min_created=min_created,
            max_created=max_created
        )
        
        return {
            "success": True,
            "count": reviews_data.get("count", 0),
            "results": reviews_data.get("results", [])
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"Error retrieving reviews for listing: {str(e)}"
        }


@mcp.tool()
async def get_reviews_by_shop(
    limit: int = 25,
    offset: int = 0,
    min_created: int = None,
    max_created: int = None
) -> dict:
    """
    Get all reviews for your Etsy shop.
    
    Reviews provide valuable feedback from buyers about their purchase experience.
    This endpoint retrieves all transaction reviews across all listings in your shop.
    
    Args:
        limit: Number of results to return (1-100). Default is 25.
        offset: Offset for pagination. Default is 0.
        min_created: The earliest unix timestamp for when a review was created (optional)
        max_created: The latest unix timestamp for when a review was created (optional)
    
    Returns:
        Dictionary containing:
        - success: Whether the request was successful
        - count: Total number of reviews
        - results: Array of review objects with details like:
          - rating: Review rating
          - review: Review text
          - language: Language code
          - buyer_user_id: ID of the buyer who left the review
          - listing_id: ID of the listing that was reviewed
          - create_timestamp: When the review was created
          - created_timestamp: When the review was created
          - update_timestamp: When the review was last updated
          - updated_timestamp: When the review was last updated
    
    Example:
        - Get all reviews: get_reviews_by_shop()
        - Get recent reviews: get_reviews_by_shop(min_created=1609459200)
        - Get paginated reviews: get_reviews_by_shop(limit=50, offset=0)
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
        
        # Validate limit
        if limit < 1 or limit > 100:
            return {
                "success": False,
                "error": "Limit must be between 1 and 100."
            }
        
        reviews_data = await etsy_client.get_reviews_by_shop(
            str(shop_id),
            limit=limit,
            offset=offset,
            min_created=min_created,
            max_created=max_created
        )
        
        return {
            "success": True,
            "count": reviews_data.get("count", 0),
            "results": reviews_data.get("results", [])
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"Error retrieving shop reviews: {str(e)}"
        }


# Payment & Financial Data Tools

@mcp.tool()
async def get_payment_ledger_entries(
    min_created: int,
    max_created: int,
    limit: int = 25,
    offset: int = 0
) -> dict:
    """
    Get payment account ledger entries for your shop.
    
    Ledger entries track all financial transactions in your payment account.
    
    Args:
        min_created: The earliest unix timestamp for when a record was created (required)
        max_created: The latest unix timestamp for when a record was created (required)
        limit: Number of results to return (1-100). Default is 25.
        offset: Offset for pagination. Default is 0.
    
    Returns:
        Dictionary containing:
        - success: Whether the request was successful
        - count: Total number of ledger entries
        - results: Array of ledger entry objects
    
    Example:
        - Get entries for a date range: get_payment_ledger_entries(min_created=1609459200, max_created=1640995200)
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
        
        # Validate limit
        if limit < 1 or limit > 100:
            return {
                "success": False,
                "error": "Limit must be between 1 and 100."
            }
        
        # Validate timestamps (minimum timestamp per API: 946684800)
        if min_created < 946684800 or max_created < 946684800:
            return {
                "success": False,
                "error": "Timestamps must be >= 946684800 (Jan 1, 2000)."
            }
        
        ledger_data = await etsy_client.get_payment_ledger_entries(
            str(shop_id),
            min_created=min_created,
            max_created=max_created,
            limit=limit,
            offset=offset
        )
        
        return {
            "success": True,
            "count": ledger_data.get("count", 0),
            "results": ledger_data.get("results", [])
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"Error retrieving ledger entries: {str(e)}"
        }


@mcp.tool()
async def get_payment_by_receipt(receipt_id: int) -> dict:
    """
    Get payment details for a specific receipt/order.
    
    Args:
        receipt_id: The numeric ID of the receipt
    
    Returns:
        Dictionary containing:
        - success: Whether the request was successful
        - payment: Payment object with transaction details
    
    Example:
        - Get payment for order: get_payment_by_receipt(receipt_id=123456789)
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
        
        payment_data = await etsy_client.get_payment_by_receipt(str(shop_id), str(receipt_id))
        
        return {
            "success": True,
            "payment": payment_data
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"Error retrieving payment: {str(e)}"
        }


@mcp.tool()
async def get_shop_payments(payment_ids: list = None) -> dict:
    """
    Get shop payments, optionally filtered by payment IDs.
    
    Args:
        payment_ids: Optional list of payment ID integers to retrieve
    
    Returns:
        Dictionary containing:
        - success: Whether the request was successful
        - count: Number of payments
        - results: Array of payment objects
    
    Example:
        - Get specific payments: get_shop_payments(payment_ids=[123, 456, 789])
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
        
        if payment_ids is not None and not payment_ids:
            return {
                "success": False,
                "error": "payment_ids list cannot be empty. Either provide IDs or omit the parameter."
            }
        
        payments_data = await etsy_client.get_payments(str(shop_id), payment_ids=payment_ids)
        
        return {
            "success": True,
            "count": payments_data.get("count", 0),
            "results": payments_data.get("results", [])
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"Error retrieving payments: {str(e)}"
        }


@mcp.tool()
async def get_ledger_entry_payments(ledger_entry_ids: list) -> dict:
    """
    Get payments associated with specific ledger entry IDs.
    
    Args:
        ledger_entry_ids: List of ledger entry ID integers (required)
    
    Returns:
        Dictionary containing:
        - success: Whether the request was successful
        - count: Number of payments
        - results: Array of payment objects
    
    Example:
        - Get payments for entries: get_ledger_entry_payments(ledger_entry_ids=[123, 456])
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
        
        if not ledger_entry_ids:
            return {
                "success": False,
                "error": "ledger_entry_ids parameter is required and cannot be empty."
            }
        
        payments_data = await etsy_client.get_ledger_entry_payments(
            str(shop_id), 
            ledger_entry_ids=ledger_entry_ids
        )
        
        return {
            "success": True,
            "count": payments_data.get("count", 0),
            "results": payments_data.get("results", [])
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"Error retrieving ledger entry payments: {str(e)}"
        }


# Shipping Profile Management Tools

@mcp.tool()
async def get_shipping_carriers(origin_country_iso: str) -> dict:
    """
    Get available shipping carriers and mail classes for a country.
    
    This helps you determine which carriers and mail classes to use when creating
    or updating shipping profiles and destinations.
    
    Args:
        origin_country_iso: The ISO code of the country (e.g., "US", "GB", "CA")
    
    Returns:
        Dictionary containing:
        - success: Whether the request was successful
        - results: Array of shipping carriers with their mail classes
    
    Example:
        - Get US carriers: get_shipping_carriers(origin_country_iso="US")
    """
    if etsy_client is None:
        return {
            "success": False,
            "error": "Not connected to Etsy. Please use connect_etsy tool first."
        }
    
    try:
        carriers_data = await etsy_client.get_shipping_carriers(origin_country_iso)
        
        return {
            "success": True,
            "results": carriers_data.get("results", [])
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"Error retrieving shipping carriers: {str(e)}"
        }


@mcp.tool()
async def create_shipping_profile(
    title: str,
    origin_country_iso: str,
    primary_cost: float,
    secondary_cost: float,
    min_processing_time: int = None,
    max_processing_time: int = None,
    processing_time_unit: str = "business_days",
    destination_country_iso: str = None,
    destination_region: str = None,
    origin_postal_code: str = None,
    shipping_carrier_id: int = None,
    mail_class: str = None,
    min_delivery_days: int = None,
    max_delivery_days: int = None
) -> dict:
    """
    Create a new shipping profile for your shop.
    
    You must provide either (shipping_carrier_id AND mail_class) OR (min_delivery_days AND max_delivery_days).
    You must provide either destination_country_iso OR destination_region (not both).
    
    Args:
        title: Name of the shipping profile
        origin_country_iso: ISO code of country from which items ship (e.g., "US")
        primary_cost: Cost of shipping to this destination alone
        secondary_cost: Cost of shipping with another item
        min_processing_time: Minimum processing time (1-10)
        max_processing_time: Maximum processing time (1-10)
        processing_time_unit: "business_days" or "weeks" (default: "business_days")
        destination_country_iso: ISO code of destination country (XOR with destination_region)
        destination_region: "eu", "non_eu", or "none" (XOR with destination_country_iso)
        origin_postal_code: Postal code for origin location (required for some countries)
        shipping_carrier_id: Carrier ID (use get_shipping_carriers to find)
        mail_class: Mail class (use get_shipping_carriers to find)
        min_delivery_days: Minimum delivery days (1-45)
        max_delivery_days: Maximum delivery days (1-45)
    
    Returns:
        Dictionary containing:
        - success: Whether creation was successful
        - message: Confirmation message
        - profile: Created shipping profile object
    
    Example:
        - Create with carrier: create_shipping_profile(title="Standard", origin_country_iso="US", 
                                primary_cost=5.0, secondary_cost=2.0, shipping_carrier_id=123, mail_class="usps_first")
        - Create with delivery days: create_shipping_profile(title="Standard", origin_country_iso="US",
                                      primary_cost=5.0, secondary_cost=2.0, min_delivery_days=3, max_delivery_days=7)
    """
    if etsy_client is None:
        return {
            "success": False,
            "error": "Not connected to Etsy. Please use connect_etsy tool first."
        }
    
    try:
        # Validate mutually exclusive destination parameters
        if destination_country_iso and destination_region:
            return {
                "success": False,
                "error": "Cannot specify both destination_country_iso and destination_region. Choose one or the other."
            }
        
        # Validate delivery method specification
        has_carrier = shipping_carrier_id is not None and mail_class is not None
        has_delivery_days = min_delivery_days is not None and max_delivery_days is not None
        
        if not has_carrier and not has_delivery_days:
            return {
                "success": False,
                "error": "Must provide either (shipping_carrier_id AND mail_class) OR (min_delivery_days AND max_delivery_days)."
            }
        
        user_data = await etsy_client.get_current_user()
        shop_id = user_data.get("shop_id")
        
        if not shop_id:
            return {
                "success": False,
                "error": "No shop_id found for this user."
            }
        
        profile_data = await etsy_client.create_shipping_profile(
            str(shop_id),
            title=title,
            origin_country_iso=origin_country_iso,
            primary_cost=primary_cost,
            secondary_cost=secondary_cost,
            min_processing_time=min_processing_time,
            max_processing_time=max_processing_time,
            processing_time_unit=processing_time_unit,
            destination_country_iso=destination_country_iso,
            destination_region=destination_region,
            origin_postal_code=origin_postal_code,
            shipping_carrier_id=shipping_carrier_id,
            mail_class=mail_class,
            min_delivery_days=min_delivery_days,
            max_delivery_days=max_delivery_days
        )
        
        return {
            "success": True,
            "message": f"Successfully created shipping profile '{title}'",
            "profile": profile_data
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"Error creating shipping profile: {str(e)}"
        }


@mcp.tool()
async def update_shipping_profile(
    shipping_profile_id: int,
    title: str = None,
    origin_country_iso: str = None,
    min_processing_time: int = None,
    max_processing_time: int = None,
    processing_time_unit: str = None,
    origin_postal_code: str = None
) -> dict:
    """
    Update an existing shipping profile.
    
    Args:
        shipping_profile_id: The numeric ID of the shipping profile to update
        title: Name of the shipping profile
        origin_country_iso: ISO code of country from which items ship
        min_processing_time: Minimum processing time (1-10)
        max_processing_time: Maximum processing time (1-10)
        processing_time_unit: "business_days" or "weeks"
        origin_postal_code: Postal code for origin location
    
    Returns:
        Dictionary containing:
        - success: Whether update was successful
        - message: Confirmation message
        - profile: Updated shipping profile object
    
    Example:
        - Update processing time: update_shipping_profile(shipping_profile_id=123, min_processing_time=1, max_processing_time=3)
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
        
        # Check that at least one parameter is provided
        if all(p is None for p in [title, origin_country_iso, min_processing_time, 
                                     max_processing_time, processing_time_unit, origin_postal_code]):
            return {
                "success": False,
                "error": "At least one parameter must be provided to update."
            }
        
        profile_data = await etsy_client.update_shipping_profile(
            str(shop_id),
            str(shipping_profile_id),
            title=title,
            origin_country_iso=origin_country_iso,
            min_processing_time=min_processing_time,
            max_processing_time=max_processing_time,
            processing_time_unit=processing_time_unit,
            origin_postal_code=origin_postal_code
        )
        
        return {
            "success": True,
            "message": f"Successfully updated shipping profile {shipping_profile_id}",
            "profile": profile_data
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"Error updating shipping profile: {str(e)}"
        }


@mcp.tool()
async def delete_shipping_profile(shipping_profile_id: int) -> dict:
    """
    Delete a shipping profile from your shop.
    
    Args:
        shipping_profile_id: The numeric ID of the shipping profile to delete
    
    Returns:
        Dictionary containing:
        - success: Whether deletion was successful
        - message: Confirmation message
    
    Example:
        - Delete profile: delete_shipping_profile(shipping_profile_id=123)
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
        
        await etsy_client.delete_shipping_profile(str(shop_id), str(shipping_profile_id))
        
        return {
            "success": True,
            "message": f"Successfully deleted shipping profile {shipping_profile_id}"
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"Error deleting shipping profile: {str(e)}"
        }


# Shipping Profile Destination Tools

@mcp.tool()
async def create_shipping_profile_destination(
    shipping_profile_id: int,
    primary_cost: float,
    secondary_cost: float,
    destination_country_iso: str = None,
    destination_region: str = None,
    shipping_carrier_id: int = None,
    mail_class: str = None,
    min_delivery_days: int = None,
    max_delivery_days: int = None
) -> dict:
    """
    Add a shipping destination to an existing shipping profile.
    
    You must provide either destination_country_iso OR destination_region (not both).
    You must provide either (shipping_carrier_id AND mail_class) OR (min_delivery_days AND max_delivery_days).
    
    Args:
        shipping_profile_id: The numeric ID of the shipping profile
        primary_cost: Cost of shipping to this destination alone
        secondary_cost: Cost of shipping with another item
        destination_country_iso: ISO code of destination country (XOR with destination_region)
        destination_region: "eu", "non_eu", or "none" (XOR with destination_country_iso)
        shipping_carrier_id: Carrier ID
        mail_class: Mail class
        min_delivery_days: Minimum delivery days (1-45)
        max_delivery_days: Maximum delivery days (1-45)
    
    Returns:
        Dictionary containing:
        - success: Whether creation was successful
        - message: Confirmation message
        - destination: Created destination object
    
    Example:
        - Add US destination: create_shipping_profile_destination(shipping_profile_id=123, 
                              primary_cost=10.0, secondary_cost=5.0, destination_country_iso="US",
                              min_delivery_days=3, max_delivery_days=7)
    """
    if etsy_client is None:
        return {
            "success": False,
            "error": "Not connected to Etsy. Please use connect_etsy tool first."
        }
    
    try:
        # Validate mutually exclusive destination parameters
        if destination_country_iso and destination_region:
            return {
                "success": False,
                "error": "Cannot specify both destination_country_iso and destination_region. Choose one or the other."
            }
        
        # Validate delivery method specification
        has_carrier = shipping_carrier_id is not None and mail_class is not None
        has_delivery_days = min_delivery_days is not None and max_delivery_days is not None
        
        if not has_carrier and not has_delivery_days:
            return {
                "success": False,
                "error": "Must provide either (shipping_carrier_id AND mail_class) OR (min_delivery_days AND max_delivery_days)."
            }
        
        user_data = await etsy_client.get_current_user()
        shop_id = user_data.get("shop_id")
        
        if not shop_id:
            return {
                "success": False,
                "error": "No shop_id found for this user."
            }
        
        destination_data = await etsy_client.create_shipping_profile_destination(
            str(shop_id),
            str(shipping_profile_id),
            primary_cost=primary_cost,
            secondary_cost=secondary_cost,
            destination_country_iso=destination_country_iso,
            destination_region=destination_region,
            shipping_carrier_id=shipping_carrier_id,
            mail_class=mail_class,
            min_delivery_days=min_delivery_days,
            max_delivery_days=max_delivery_days
        )
        
        return {
            "success": True,
            "message": f"Successfully created shipping destination for profile {shipping_profile_id}",
            "destination": destination_data
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"Error creating shipping destination: {str(e)}"
        }


@mcp.tool()
async def get_shipping_profile_destinations(
    shipping_profile_id: int,
    limit: int = 25,
    offset: int = 0
) -> dict:
    """
    Get all shipping destinations for a shipping profile.
    
    Args:
        shipping_profile_id: The numeric ID of the shipping profile
        limit: Number of results to return (1-100). Default is 25.
        offset: Offset for pagination. Default is 0.
    
    Returns:
        Dictionary containing:
        - success: Whether the request was successful
        - count: Number of destinations
        - results: Array of destination objects
    
    Example:
        - Get destinations: get_shipping_profile_destinations(shipping_profile_id=123)
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
        
        destinations_data = await etsy_client.get_shipping_profile_destinations(
            str(shop_id),
            str(shipping_profile_id),
            limit=limit,
            offset=offset
        )
        
        return {
            "success": True,
            "count": destinations_data.get("count", 0),
            "results": destinations_data.get("results", [])
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"Error retrieving shipping destinations: {str(e)}"
        }


@mcp.tool()
async def update_shipping_profile_destination(
    shipping_profile_id: int,
    destination_id: int,
    primary_cost: float = None,
    secondary_cost: float = None,
    destination_country_iso: str = None,
    destination_region: str = None,
    shipping_carrier_id: int = None,
    mail_class: str = None,
    min_delivery_days: int = None,
    max_delivery_days: int = None
) -> dict:
    """
    Update an existing shipping destination.
    
    Args:
        shipping_profile_id: The numeric ID of the shipping profile
        destination_id: The numeric ID of the destination to update
        primary_cost: Cost of shipping to this destination alone
        secondary_cost: Cost of shipping with another item
        destination_country_iso: ISO code of destination country
        destination_region: "eu", "non_eu", or "none"
        shipping_carrier_id: Carrier ID
        mail_class: Mail class
        min_delivery_days: Minimum delivery days (1-45)
        max_delivery_days: Maximum delivery days (1-45)
    
    Returns:
        Dictionary containing:
        - success: Whether update was successful
        - message: Confirmation message
        - destination: Updated destination object
    
    Example:
        - Update costs: update_shipping_profile_destination(shipping_profile_id=123, 
                        destination_id=456, primary_cost=12.0, secondary_cost=6.0)
    """
    if etsy_client is None:
        return {
            "success": False,
            "error": "Not connected to Etsy. Please use connect_etsy tool first."
        }
    
    try:
        # Validate mutually exclusive destination parameters
        if destination_country_iso and destination_region:
            return {
                "success": False,
                "error": "Cannot specify both destination_country_iso and destination_region."
            }
        
        user_data = await etsy_client.get_current_user()
        shop_id = user_data.get("shop_id")
        
        if not shop_id:
            return {
                "success": False,
                "error": "No shop_id found for this user."
            }
        
        destination_data = await etsy_client.update_shipping_profile_destination(
            str(shop_id),
            str(shipping_profile_id),
            str(destination_id),
            primary_cost=primary_cost,
            secondary_cost=secondary_cost,
            destination_country_iso=destination_country_iso,
            destination_region=destination_region,
            shipping_carrier_id=shipping_carrier_id,
            mail_class=mail_class,
            min_delivery_days=min_delivery_days,
            max_delivery_days=max_delivery_days
        )
        
        return {
            "success": True,
            "message": f"Successfully updated shipping destination {destination_id}",
            "destination": destination_data
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"Error updating shipping destination: {str(e)}"
        }


@mcp.tool()
async def delete_shipping_profile_destination(
    shipping_profile_id: int,
    destination_id: int
) -> dict:
    """
    Delete a shipping destination from a shipping profile.
    
    Note: A shipping profile must have at least one destination. This will fail
    if you try to delete the last destination. Delete the entire profile instead.
    
    Args:
        shipping_profile_id: The numeric ID of the shipping profile
        destination_id: The numeric ID of the destination to delete
    
    Returns:
        Dictionary containing:
        - success: Whether deletion was successful
        - message: Confirmation message
    
    Example:
        - Delete destination: delete_shipping_profile_destination(shipping_profile_id=123, destination_id=456)
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
        
        await etsy_client.delete_shipping_profile_destination(
            str(shop_id),
            str(shipping_profile_id),
            str(destination_id)
        )
        
        return {
            "success": True,
            "message": f"Successfully deleted shipping destination {destination_id}"
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"Error deleting shipping destination: {str(e)}"
        }


# Shipping Profile Upgrade Tools

@mcp.tool()
async def create_shipping_profile_upgrade(
    shipping_profile_id: int,
    upgrade_type: str,
    upgrade_name: str,
    price: float,
    secondary_price: float,
    shipping_carrier_id: int = None,
    mail_class: str = None,
    min_delivery_days: int = None,
    max_delivery_days: int = None
) -> dict:
    """
    Add a shipping upgrade option to a shipping profile.
    
    Shipping upgrades allow buyers to choose faster or premium shipping options.
    You must provide either (shipping_carrier_id AND mail_class) OR (min_delivery_days AND max_delivery_days).
    
    Args:
        shipping_profile_id: The numeric ID of the shipping profile
        upgrade_type: "0" for domestic, "1" for international
        upgrade_name: Name shown to shoppers (e.g., "USPS Priority", "Express")
        price: Additional cost for the upgrade
        secondary_price: Additional cost for each additional item
        shipping_carrier_id: Carrier ID
        mail_class: Mail class
        min_delivery_days: Minimum delivery days (1-45)
        max_delivery_days: Maximum delivery days (1-45)
    
    Returns:
        Dictionary containing:
        - success: Whether creation was successful
        - message: Confirmation message
        - upgrade: Created upgrade object
    
    Example:
        - Add express upgrade: create_shipping_profile_upgrade(shipping_profile_id=123,
                               upgrade_type="0", upgrade_name="Express", price=15.0, 
                               secondary_price=10.0, min_delivery_days=1, max_delivery_days=2)
    """
    if etsy_client is None:
        return {
            "success": False,
            "error": "Not connected to Etsy. Please use connect_etsy tool first."
        }
    
    try:
        # Validate upgrade_type
        if upgrade_type not in ["0", "1"]:
            return {
                "success": False,
                "error": "upgrade_type must be '0' (domestic) or '1' (international)."
            }
        
        # Validate delivery method specification
        has_carrier = shipping_carrier_id is not None and mail_class is not None
        has_delivery_days = min_delivery_days is not None and max_delivery_days is not None
        
        if not has_carrier and not has_delivery_days:
            return {
                "success": False,
                "error": "Must provide either (shipping_carrier_id AND mail_class) OR (min_delivery_days AND max_delivery_days)."
            }
        
        user_data = await etsy_client.get_current_user()
        shop_id = user_data.get("shop_id")
        
        if not shop_id:
            return {
                "success": False,
                "error": "No shop_id found for this user."
            }
        
        upgrade_data = await etsy_client.create_shipping_profile_upgrade(
            str(shop_id),
            str(shipping_profile_id),
            upgrade_type=upgrade_type,
            upgrade_name=upgrade_name,
            price=price,
            secondary_price=secondary_price,
            shipping_carrier_id=shipping_carrier_id,
            mail_class=mail_class,
            min_delivery_days=min_delivery_days,
            max_delivery_days=max_delivery_days
        )
        
        return {
            "success": True,
            "message": f"Successfully created shipping upgrade '{upgrade_name}'",
            "upgrade": upgrade_data
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"Error creating shipping upgrade: {str(e)}"
        }


@mcp.tool()
async def get_shipping_profile_upgrades(shipping_profile_id: int) -> dict:
    """
    Get all shipping upgrades for a shipping profile.
    
    Args:
        shipping_profile_id: The numeric ID of the shipping profile
    
    Returns:
        Dictionary containing:
        - success: Whether the request was successful
        - count: Number of upgrades
        - results: Array of upgrade objects
    
    Example:
        - Get upgrades: get_shipping_profile_upgrades(shipping_profile_id=123)
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
        
        upgrades_data = await etsy_client.get_shipping_profile_upgrades(
            str(shop_id),
            str(shipping_profile_id)
        )
        
        return {
            "success": True,
            "count": upgrades_data.get("count", 0),
            "results": upgrades_data.get("results", [])
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"Error retrieving shipping upgrades: {str(e)}"
        }


@mcp.tool()
async def update_shipping_profile_upgrade(
    shipping_profile_id: int,
    upgrade_id: int,
    upgrade_name: str = None,
    upgrade_type: str = None,
    price: float = None,
    secondary_price: float = None,
    shipping_carrier_id: int = None,
    mail_class: str = None,
    min_delivery_days: int = None,
    max_delivery_days: int = None
) -> dict:
    """
    Update an existing shipping upgrade.
    
    Args:
        shipping_profile_id: The numeric ID of the shipping profile
        upgrade_id: The numeric ID of the upgrade to update
        upgrade_name: Name shown to shoppers
        upgrade_type: "0" for domestic, "1" for international
        price: Additional cost for the upgrade
        secondary_price: Additional cost for each additional item
        shipping_carrier_id: Carrier ID
        mail_class: Mail class
        min_delivery_days: Minimum delivery days (1-45)
        max_delivery_days: Maximum delivery days (1-45)
    
    Returns:
        Dictionary containing:
        - success: Whether update was successful
        - message: Confirmation message
        - upgrade: Updated upgrade object
    
    Example:
        - Update price: update_shipping_profile_upgrade(shipping_profile_id=123, 
                        upgrade_id=456, price=20.0, secondary_price=15.0)
    """
    if etsy_client is None:
        return {
            "success": False,
            "error": "Not connected to Etsy. Please use connect_etsy tool first."
        }
    
    try:
        # Validate upgrade_type if provided
        if upgrade_type is not None and upgrade_type not in ["0", "1"]:
            return {
                "success": False,
                "error": "upgrade_type must be '0' (domestic) or '1' (international)."
            }
        
        user_data = await etsy_client.get_current_user()
        shop_id = user_data.get("shop_id")
        
        if not shop_id:
            return {
                "success": False,
                "error": "No shop_id found for this user."
            }
        
        upgrade_data = await etsy_client.update_shipping_profile_upgrade(
            str(shop_id),
            str(shipping_profile_id),
            str(upgrade_id),
            upgrade_name=upgrade_name,
            upgrade_type=upgrade_type,
            price=price,
            secondary_price=secondary_price,
            shipping_carrier_id=shipping_carrier_id,
            mail_class=mail_class,
            min_delivery_days=min_delivery_days,
            max_delivery_days=max_delivery_days
        )
        
        return {
            "success": True,
            "message": f"Successfully updated shipping upgrade {upgrade_id}",
            "upgrade": upgrade_data
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"Error updating shipping upgrade: {str(e)}"
        }


@mcp.tool()
async def delete_shipping_profile_upgrade(
    shipping_profile_id: int,
    upgrade_id: int
) -> dict:
    """
    Delete a shipping upgrade from a shipping profile.
    
    Args:
        shipping_profile_id: The numeric ID of the shipping profile
        upgrade_id: The numeric ID of the upgrade to delete
    
    Returns:
        Dictionary containing:
        - success: Whether deletion was successful
        - message: Confirmation message
    
    Example:
        - Delete upgrade: delete_shipping_profile_upgrade(shipping_profile_id=123, upgrade_id=456)
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
        
        await etsy_client.delete_shipping_profile_upgrade(
            str(shop_id),
            str(shipping_profile_id),
            str(upgrade_id)
        )
        
        return {
            "success": True,
            "message": f"Successfully deleted shipping upgrade {upgrade_id}"
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"Error deleting shipping upgrade: {str(e)}"
        }


# Return Policy Management Tools

@mcp.tool()
async def get_return_policies() -> dict:
    """
    Get all return policies for your shop.
    
    Returns:
        Dictionary containing:
        - success: Whether the request was successful
        - count: Number of return policies
        - results: Array of return policy objects
    
    Example:
        - Get all policies: get_return_policies()
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
        
        policies_data = await etsy_client.get_return_policies(str(shop_id))
        
        return {
            "success": True,
            "count": policies_data.get("count", 0),
            "results": policies_data.get("results", [])
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"Error retrieving return policies: {str(e)}"
        }


@mcp.tool()
async def get_return_policy(return_policy_id: int) -> dict:
    """
    Get a specific return policy by ID.
    
    Args:
        return_policy_id: The numeric ID of the return policy
    
    Returns:
        Dictionary containing:
        - success: Whether the request was successful
        - policy: Return policy object
    
    Example:
        - Get policy: get_return_policy(return_policy_id=123)
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
        
        policy_data = await etsy_client.get_return_policy(str(shop_id), str(return_policy_id))
        
        return {
            "success": True,
            "policy": policy_data
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"Error retrieving return policy: {str(e)}"
        }


@mcp.tool()
async def create_return_policy(
    accepts_returns: bool,
    accepts_exchanges: bool,
    return_deadline: int = None
) -> dict:
    """
    Create a new return policy for your shop.
    
    If either accepts_returns or accepts_exchanges is True, then return_deadline is required.
    
    Args:
        accepts_returns: Whether the shop accepts returns
        accepts_exchanges: Whether the shop accepts exchanges
        return_deadline: Days for return deadline. Must be one of: 7, 14, 21, 30, 45, 60, 90.
                         Required if either accepts flag is True.
    
    Returns:
        Dictionary containing:
        - success: Whether creation was successful
        - message: Confirmation message
        - policy: Created return policy object
    
    Example:
        - Create policy: create_return_policy(accepts_returns=True, accepts_exchanges=False, return_deadline=30)
    """
    if etsy_client is None:
        return {
            "success": False,
            "error": "Not connected to Etsy. Please use connect_etsy tool first."
        }
    
    try:
        # Validate return_deadline requirement
        if (accepts_returns or accepts_exchanges) and return_deadline is None:
            return {
                "success": False,
                "error": "return_deadline is required when accepts_returns or accepts_exchanges is True."
            }
        
        # Validate return_deadline value
        if return_deadline is not None and return_deadline not in [7, 14, 21, 30, 45, 60, 90]:
            return {
                "success": False,
                "error": "return_deadline must be one of: 7, 14, 21, 30, 45, 60, 90."
            }
        
        user_data = await etsy_client.get_current_user()
        shop_id = user_data.get("shop_id")
        
        if not shop_id:
            return {
                "success": False,
                "error": "No shop_id found for this user."
            }
        
        policy_data = await etsy_client.create_return_policy(
            str(shop_id),
            accepts_returns=accepts_returns,
            accepts_exchanges=accepts_exchanges,
            return_deadline=return_deadline
        )
        
        return {
            "success": True,
            "message": "Successfully created return policy",
            "policy": policy_data
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"Error creating return policy: {str(e)}"
        }


@mcp.tool()
async def update_return_policy(
    return_policy_id: int,
    accepts_returns: bool,
    accepts_exchanges: bool,
    return_deadline: int = None
) -> dict:
    """
    Update an existing return policy.
    
    If either accepts_returns or accepts_exchanges is True, then return_deadline is required.
    
    Args:
        return_policy_id: The numeric ID of the return policy to update
        accepts_returns: Whether the shop accepts returns
        accepts_exchanges: Whether the shop accepts exchanges
        return_deadline: Days for return deadline. Must be one of: 7, 14, 21, 30, 45, 60, 90.
                         Required if either accepts flag is True.
    
    Returns:
        Dictionary containing:
        - success: Whether update was successful
        - message: Confirmation message
        - policy: Updated return policy object
    
    Example:
        - Update policy: update_return_policy(return_policy_id=123, accepts_returns=True, 
                         accepts_exchanges=True, return_deadline=30)
    """
    if etsy_client is None:
        return {
            "success": False,
            "error": "Not connected to Etsy. Please use connect_etsy tool first."
        }
    
    try:
        # Validate return_deadline requirement
        if (accepts_returns or accepts_exchanges) and return_deadline is None:
            return {
                "success": False,
                "error": "return_deadline is required when accepts_returns or accepts_exchanges is True."
            }
        
        # Validate return_deadline value
        if return_deadline is not None and return_deadline not in [7, 14, 21, 30, 45, 60, 90]:
            return {
                "success": False,
                "error": "return_deadline must be one of: 7, 14, 21, 30, 45, 60, 90."
            }
        
        user_data = await etsy_client.get_current_user()
        shop_id = user_data.get("shop_id")
        
        if not shop_id:
            return {
                "success": False,
                "error": "No shop_id found for this user."
            }
        
        policy_data = await etsy_client.update_return_policy(
            str(shop_id),
            str(return_policy_id),
            accepts_returns=accepts_returns,
            accepts_exchanges=accepts_exchanges,
            return_deadline=return_deadline
        )
        
        return {
            "success": True,
            "message": f"Successfully updated return policy {return_policy_id}",
            "policy": policy_data
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"Error updating return policy: {str(e)}"
        }


@mcp.tool()
async def delete_return_policy(return_policy_id: int) -> dict:
    """
    Delete a return policy from your shop.
    
    Note: A return policy can only be deleted if no listings are using it.
    Move listings to another policy before deleting.
    
    Args:
        return_policy_id: The numeric ID of the return policy to delete
    
    Returns:
        Dictionary containing:
        - success: Whether deletion was successful
        - message: Confirmation message
    
    Example:
        - Delete policy: delete_return_policy(return_policy_id=123)
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
        
        await etsy_client.delete_return_policy(str(shop_id), str(return_policy_id))
        
        return {
            "success": True,
            "message": f"Successfully deleted return policy {return_policy_id}"
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"Error deleting return policy: {str(e)}"
        }


@mcp.tool()
async def consolidate_return_policies(
    source_return_policy_id: int,
    destination_return_policy_id: int
) -> dict:
    """
    Consolidate return policies by moving all listings from source to destination policy,
    then deleting the source policy.
    
    This is commonly used when updating a policy would create a duplicate.
    
    Args:
        source_return_policy_id: The numeric ID of the source return policy to consolidate from
        destination_return_policy_id: The numeric ID of the destination return policy to move listings to
    
    Returns:
        Dictionary containing:
        - success: Whether consolidation was successful
        - message: Confirmation message
        - policy: Updated destination return policy object
    
    Example:
        - Consolidate policies: consolidate_return_policies(source_return_policy_id=123, 
                                destination_return_policy_id=456)
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
        
        policy_data = await etsy_client.consolidate_return_policies(
            str(shop_id),
            str(source_return_policy_id),
            str(destination_return_policy_id)
        )
        
        return {
            "success": True,
            "message": f"Successfully consolidated return policies (moved from {source_return_policy_id} to {destination_return_policy_id})",
            "policy": policy_data
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"Error consolidating return policies: {str(e)}"
        }


# Shop Update Tools

@mcp.tool()
async def update_shop(
    title: str = None,
    announcement: str = None,
    sale_message: str = None,
    digital_sale_message: str = None,
    policy_additional: str = None
) -> dict:
    """
    Update your shop information.
    
    Args:
        title: Shop title/heading displayed on shop homepage
        announcement: Shop announcement displayed on homepage
        sale_message: Message sent to buyers who complete a purchase
        digital_sale_message: Message sent to buyers who purchase digital items
        policy_additional: Additional shop policies (EU shops only)
    
    Returns:
        Dictionary containing:
        - success: Whether update was successful
        - message: Confirmation message
        - shop: Updated shop object
    
    Example:
        - Update announcement: update_shop(announcement="Holiday sale - 20% off everything!")
        - Update multiple fields: update_shop(title="My Awesome Shop", announcement="Welcome!")
    """
    if etsy_client is None:
        return {
            "success": False,
            "error": "Not connected to Etsy. Please use connect_etsy tool first."
        }
    
    try:
        # Check that at least one parameter is provided
        if all(p is None for p in [title, announcement, sale_message, digital_sale_message, policy_additional]):
            return {
                "success": False,
                "error": "At least one parameter must be provided to update."
            }
        
        user_data = await etsy_client.get_current_user()
        shop_id = user_data.get("shop_id")
        
        if not shop_id:
            return {
                "success": False,
                "error": "No shop_id found for this user."
            }
        
        shop_data = await etsy_client.update_shop(
            str(shop_id),
            title=title,
            announcement=announcement,
            sale_message=sale_message,
            digital_sale_message=digital_sale_message,
            policy_additional=policy_additional
        )
        
        return {
            "success": True,
            "message": "Successfully updated shop information",
            "shop": shop_data
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"Error updating shop: {str(e)}"
        }


@mcp.tool()
async def get_holiday_preferences() -> dict:
    """
    Get your shop's holiday preferences.
    
    Holiday preferences determine whether your shop processes orders on specific holidays.
    Currently only supported for US and CA shops.
    
    Returns:
        Dictionary containing:
        - success: Whether the request was successful
        - count: Number of holiday preferences
        - results: Array of holiday preference objects
    
    Example:
        - Get preferences: get_holiday_preferences()
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
        
        preferences_data = await etsy_client.get_holiday_preferences(str(shop_id))
        
        # Handle list response (not paginated)
        if isinstance(preferences_data, list):
            return {
                "success": True,
                "count": len(preferences_data),
                "results": preferences_data
            }
        else:
            return {
                "success": True,
                "count": preferences_data.get("count", 0),
                "results": preferences_data.get("results", [])
            }
    except Exception as e:
        return {
            "success": False,
            "error": f"Error retrieving holiday preferences: {str(e)}"
        }


@mcp.tool()
async def update_holiday_preference(
    holiday_id: int,
    is_working: bool
) -> dict:
    """
    Update whether your shop processes orders on a specific holiday.
    
    Currently only supported for US and CA shops.
    
    Args:
        holiday_id: The numeric ID of the holiday (1-105)
        is_working: Whether the shop will process orders on this holiday
    
    Returns:
        Dictionary containing:
        - success: Whether update was successful
        - message: Confirmation message
        - preference: Updated holiday preference object
    
    Example:
        - Set working on holiday: update_holiday_preference(holiday_id=1, is_working=True)
        - Set not working: update_holiday_preference(holiday_id=1, is_working=False)
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
        
        preference_data = await etsy_client.update_holiday_preference(
            str(shop_id),
            str(holiday_id),
            is_working=is_working
        )
        
        return {
            "success": True,
            "message": f"Successfully updated holiday preference for holiday {holiday_id}",
            "preference": preference_data
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"Error updating holiday preference: {str(e)}"
        }


# Receipt Management Tools

@mcp.tool()
async def get_shop_receipts(
    limit: int = 25,
    offset: int = 0,
    min_created: int = None,
    max_created: int = None,
    min_last_modified: int = None,
    max_last_modified: int = None,
    was_paid: bool = None,
    was_shipped: bool = None,
    was_delivered: bool = None,
    was_canceled: bool = None,
    sort_on: str = "created",
    sort_order: str = "desc"
) -> dict:
    """
    Get shop receipts/orders with optional filters.
    
    Args:
        limit: Number of results to return (1-100). Default is 25.
        offset: Offset for pagination. Default is 0.
        min_created: The earliest unix timestamp for when a receipt was created
        max_created: The latest unix timestamp for when a receipt was created
        min_last_modified: The earliest unix timestamp for when a receipt was modified
        max_last_modified: The latest unix timestamp for when a receipt was modified
        was_paid: Filter by payment status (True/False)
        was_shipped: Filter by shipment status (True/False)
        was_delivered: Filter by delivery status (True/False)
        was_canceled: Filter by cancellation status (True/False)
        sort_on: Sort by field. Options: 'created', 'updated', 'receipt_id'. Default: 'created'
        sort_order: Sort order. Options: 'asc', 'desc'. Default: 'desc'
    
    Returns:
        Dictionary containing:
        - success: Whether the request was successful
        - count: Total number of receipts
        - results: Array of receipt objects
    
    Example:
        - Get all receipts: get_shop_receipts()
        - Get paid receipts: get_shop_receipts(was_paid=True)
        - Get unshipped receipts: get_shop_receipts(was_shipped=False)
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
        
        # Validate limit
        if limit < 1 or limit > 100:
            return {
                "success": False,
                "error": "Limit must be between 1 and 100."
            }
        
        # Validate timestamps if provided
        if min_created is not None and min_created < 946684800:
            return {
                "success": False,
                "error": "min_created must be >= 946684800 (Jan 1, 2000)."
            }
        if max_created is not None and max_created < 946684800:
            return {
                "success": False,
                "error": "max_created must be >= 946684800 (Jan 1, 2000)."
            }
        
        receipts_data = await etsy_client.get_shop_receipts(
            str(shop_id),
            limit=limit,
            offset=offset,
            min_created=min_created,
            max_created=max_created,
            min_last_modified=min_last_modified,
            max_last_modified=max_last_modified,
            was_paid=was_paid,
            was_shipped=was_shipped,
            was_delivered=was_delivered,
            was_canceled=was_canceled,
            sort_on=sort_on,
            sort_order=sort_order
        )
        
        return {
            "success": True,
            "count": receipts_data.get("count", 0),
            "results": receipts_data.get("results", [])
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"Error retrieving shop receipts: {str(e)}"
        }


@mcp.tool()
async def get_shop_receipt(receipt_id: int) -> dict:
    """
    Get detailed information about a specific receipt/order.
    
    Args:
        receipt_id: The numeric ID of the receipt
    
    Returns:
        Dictionary containing:
        - success: Whether the request was successful
        - receipt: Receipt object with order details
    
    Example:
        - Get receipt: get_shop_receipt(receipt_id=123456789)
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
        
        receipt_data = await etsy_client.get_shop_receipt(str(shop_id), str(receipt_id))
        
        return {
            "success": True,
            "receipt": receipt_data
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"Error retrieving receipt: {str(e)}"
        }


@mcp.tool()
async def update_shop_receipt(
    receipt_id: int,
    was_shipped: bool = None,
    was_paid: bool = None
) -> dict:
    """
    Update receipt status and details.
    
    Args:
        receipt_id: The numeric ID of the receipt to update
        was_shipped: Whether the receipt has been shipped
        was_paid: Whether the receipt has been paid
    
    Returns:
        Dictionary containing:
        - success: Whether update was successful
        - message: Confirmation message
        - receipt: Updated receipt object
    
    Example:
        - Mark as shipped: update_shop_receipt(receipt_id=123456789, was_shipped=True)
    """
    if etsy_client is None:
        return {
            "success": False,
            "error": "Not connected to Etsy. Please use connect_etsy tool first."
        }
    
    try:
        # Check that at least one parameter is provided
        if was_shipped is None and was_paid is None:
            return {
                "success": False,
                "error": "At least one parameter (was_shipped or was_paid) must be provided."
            }
        
        user_data = await etsy_client.get_current_user()
        shop_id = user_data.get("shop_id")
        
        if not shop_id:
            return {
                "success": False,
                "error": "No shop_id found for this user."
            }
        
        receipt_data = await etsy_client.update_shop_receipt(
            str(shop_id),
            str(receipt_id),
            was_shipped=was_shipped,
            was_paid=was_paid
        )
        
        return {
            "success": True,
            "message": f"Successfully updated receipt {receipt_id}",
            "receipt": receipt_data
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"Error updating receipt: {str(e)}"
        }


@mcp.tool()
async def create_receipt_shipment(
    receipt_id: int,
    tracking_code: str = None,
    carrier_name: str = None,
    send_bcc: bool = False,
    note_to_buyer: str = None
) -> dict:
    """
    Mark an order as shipped with tracking information.
    
    Submits tracking information and notifies the buyer. If tracking_code and carrier_name 
    are not provided, the receipt is marked as shipped only.
    
    Args:
        receipt_id: The numeric ID of the receipt
        tracking_code: The tracking code for this shipment
        carrier_name: The carrier name (e.g., 'USPS', 'FedEx', 'UPS', or 'other')
        send_bcc: If True, send shipping notification to seller as well
        note_to_buyer: Optional message to include in buyer notification
    
    Returns:
        Dictionary containing:
        - success: Whether shipment was created successfully
        - message: Confirmation message
        - receipt: Updated receipt object with shipment info
    
    Example:
        - With tracking: create_receipt_shipment(receipt_id=123, tracking_code="1Z999...", carrier_name="UPS")
        - Mark shipped only: create_receipt_shipment(receipt_id=123)
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
        
        receipt_data = await etsy_client.create_receipt_shipment(
            str(shop_id),
            str(receipt_id),
            tracking_code=tracking_code,
            carrier_name=carrier_name,
            send_bcc=send_bcc,
            note_to_buyer=note_to_buyer
        )
        
        return {
            "success": True,
            "message": f"Successfully created shipment for receipt {receipt_id}",
            "receipt": receipt_data
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"Error creating receipt shipment: {str(e)}"
        }


# Transaction Management Tools

@mcp.tool()
async def get_shop_transactions(
    limit: int = 25,
    offset: int = 0
) -> dict:
    """
    Get all transactions for your shop.
    
    Args:
        limit: Number of results to return (1-100). Default is 25.
        offset: Offset for pagination. Default is 0.
    
    Returns:
        Dictionary containing:
        - success: Whether the request was successful
        - count: Total number of transactions
        - results: Array of transaction objects
    
    Example:
        - Get all transactions: get_shop_transactions()
        - Get paginated: get_shop_transactions(limit=50, offset=0)
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
        
        # Validate limit
        if limit < 1 or limit > 100:
            return {
                "success": False,
                "error": "Limit must be between 1 and 100."
            }
        
        transactions_data = await etsy_client.get_shop_transactions(
            str(shop_id),
            limit=limit,
            offset=offset
        )
        
        return {
            "success": True,
            "count": transactions_data.get("count", 0),
            "results": transactions_data.get("results", [])
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"Error retrieving shop transactions: {str(e)}"
        }


@mcp.tool()
async def get_shop_receipt_transactions(
    receipt_id: int
) -> dict:
    """
    Get transaction details for a specific receipt/order.
    
    Args:
        receipt_id: The numeric ID of the receipt
    
    Returns:
        Dictionary containing:
        - success: Whether the request was successful
        - count: Number of transactions
        - results: Array of transaction objects for this receipt
    
    Example:
        - Get receipt transactions: get_shop_receipt_transactions(receipt_id=123456789)
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
        
        transactions_data = await etsy_client.get_receipt_transactions(
            str(shop_id),
            str(receipt_id)
        )
        
        return {
            "success": True,
            "count": transactions_data.get("count", 0),
            "results": transactions_data.get("results", [])
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"Error retrieving receipt transactions: {str(e)}"
        }


@mcp.tool()
async def get_shop_receipt_transactions_by_listing(
    listing_id: int,
    limit: int = 25,
    offset: int = 0
) -> dict:
    """
    Get all transactions for a specific listing.
    
    Args:
        listing_id: The numeric ID of the listing
        limit: Number of results to return (1-100). Default is 25.
        offset: Offset for pagination. Default is 0.
    
    Returns:
        Dictionary containing:
        - success: Whether the request was successful
        - count: Total number of transactions
        - results: Array of transaction objects
    
    Example:
        - Get listing transactions: get_shop_receipt_transactions_by_listing(listing_id=123456789)
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
        
        # Validate limit
        if limit < 1 or limit > 100:
            return {
                "success": False,
                "error": "Limit must be between 1 and 100."
            }
        
        transactions_data = await etsy_client.get_listing_transactions(
            str(shop_id),
            str(listing_id),
            limit=limit,
            offset=offset
        )
        
        return {
            "success": True,
            "count": transactions_data.get("count", 0),
            "results": transactions_data.get("results", [])
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"Error retrieving listing transactions: {str(e)}"
        }


# Listing Creation Tools

@mcp.tool()
async def create_draft_listing(
    title: str,
    description: str,
    price: float,
    quantity: int,
    who_made: str,
    when_made: str,
    taxonomy_id: int,
    is_supply: bool = False,
    listing_type: str = "physical",
    shipping_profile_id: int = None,
    return_policy_id: int = None,
    tags: list = None,
    materials: list = None,
    shop_section_id: int = None,
    should_auto_renew: bool = None,
    is_taxable: bool = None,
    is_customizable: bool = None,
    is_personalizable: bool = None,
    personalization_is_required: bool = None,
    personalization_char_count_max: int = None,
    personalization_instructions: str = None
) -> dict:
    """
    Create a new draft listing with all required fields.
    
    Args:
        title: Listing title
        description: Product description
        price: Price in dollars (e.g., 25.00)
        quantity: Number of items available
        who_made: Who made the product. Options: 'i_did', 'someone_else', 'collective'
        when_made: When made. Options: 'made_to_order', '2020_2025', '2010_2019', '2006_2009', 
                   'before_2006', '2000_2005', '1990s', '1980s', '1970s', '1960s', '1950s', 
                   '1940s', '1930s', '1920s', '1910s', '1900s', '1800s', '1700s', 'before_1700'
        taxonomy_id: Numeric category ID (use Etsy taxonomy endpoints to find)
        is_supply: Whether this is a craft supply (vs finished product)
        listing_type: Type of listing. Options: 'physical', 'download', 'both'
        shipping_profile_id: ID of shipping profile (required for physical listings)
        return_policy_id: ID of return policy
        tags: Array of tag strings (max 13 tags)
        materials: Array of material strings
        shop_section_id: ID of shop section to assign listing to
        should_auto_renew: Auto-renew listing every 4 months
        is_taxable: Apply shop tax rates at checkout
        is_customizable: Buyers can request customization
        is_personalizable: Listing supports personalization
        personalization_is_required: Personalization is required
        personalization_char_count_max: Max characters for personalization
        personalization_instructions: Instructions for buyer personalization
    
    Returns:
        Dictionary containing:
        - success: Whether creation was successful
        - message: Confirmation message
        - listing: Created listing object
    
    Example:
        - Create basic listing: create_draft_listing(
            title="Handmade Mug", 
            description="Beautiful ceramic mug", 
            price=25.00, 
            quantity=5,
            who_made="i_did", 
            when_made="2020_2025", 
            taxonomy_id=1234
          )
    """
    if etsy_client is None:
        return {
            "success": False,
            "error": "Not connected to Etsy. Please use connect_etsy tool first."
        }
    
    try:
        # Validate who_made
        valid_who_made = ['i_did', 'someone_else', 'collective']
        if who_made not in valid_who_made:
            return {
                "success": False,
                "error": f"Invalid who_made '{who_made}'. Must be one of: {', '.join(valid_who_made)}"
            }
        
        # Validate listing_type
        valid_types = ['physical', 'download', 'both']
        if listing_type not in valid_types:
            return {
                "success": False,
                "error": f"Invalid listing_type '{listing_type}'. Must be one of: {', '.join(valid_types)}"
            }
        
        user_data = await etsy_client.get_current_user()
        shop_id = user_data.get("shop_id")
        
        if not shop_id:
            return {
                "success": False,
                "error": "No shop_id found for this user."
            }
        
        # Build kwargs for optional parameters
        kwargs = {
            "is_supply": is_supply,
            "type": listing_type
        }
        
        if shipping_profile_id is not None:
            kwargs["shipping_profile_id"] = shipping_profile_id
        if return_policy_id is not None:
            kwargs["return_policy_id"] = return_policy_id
        if tags is not None:
            kwargs["tags"] = tags
        if materials is not None:
            kwargs["materials"] = materials
        if shop_section_id is not None:
            kwargs["shop_section_id"] = shop_section_id
        if should_auto_renew is not None:
            kwargs["should_auto_renew"] = should_auto_renew
        if is_taxable is not None:
            kwargs["is_taxable"] = is_taxable
        if is_customizable is not None:
            kwargs["is_customizable"] = is_customizable
        if is_personalizable is not None:
            kwargs["is_personalizable"] = is_personalizable
        if personalization_is_required is not None:
            kwargs["personalization_is_required"] = personalization_is_required
        if personalization_char_count_max is not None:
            kwargs["personalization_char_count_max"] = personalization_char_count_max
        if personalization_instructions is not None:
            kwargs["personalization_instructions"] = personalization_instructions
        
        listing_data = await etsy_client.create_draft_listing(
            str(shop_id),
            quantity=quantity,
            title=title,
            description=description,
            price=price,
            who_made=who_made,
            when_made=when_made,
            taxonomy_id=taxonomy_id,
            **kwargs
        )
        
        return {
            "success": True,
            "message": f"Successfully created draft listing",
            "listing": listing_data
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"Error creating draft listing: {str(e)}"
        }


# Listing Image Management Tools

@mcp.tool()
async def get_listing_images(listing_id: int) -> dict:
    """
    Get all images for a listing.
    
    Args:
        listing_id: The numeric ID of the listing
    
    Returns:
        Dictionary containing:
        - success: Whether the request was successful
        - count: Number of images
        - results: Array of image objects
    
    Example:
        - Get images: get_listing_images(listing_id=123456789)
    """
    if etsy_client is None:
        return {
            "success": False,
            "error": "Not connected to Etsy. Please use connect_etsy tool first."
        }
    
    try:
        images_data = await etsy_client.get_listing_images(str(listing_id))
        
        return {
            "success": True,
            "count": images_data.get("count", 0),
            "results": images_data.get("results", [])
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"Error retrieving listing images: {str(e)}"
        }


@mcp.tool()
async def upload_listing_image(
    listing_id: int,
    image_path: str,
    rank: int = None,
    overwrite: bool = False,
    is_watermarked: bool = False,
    alt_text: str = None
) -> dict:
    """
    Upload a new image to a listing.
    
    Args:
        listing_id: The numeric ID of the listing
        image_path: Path to the image file to upload
        rank: Position in image display (1 is leftmost/primary). Default: next available
        overwrite: Replace existing image at this rank. Default: False
        is_watermarked: Image has a watermark. Default: False
        alt_text: Alt text for accessibility (max 500 characters)
    
    Returns:
        Dictionary containing:
        - success: Whether upload was successful
        - message: Confirmation message
        - image: Uploaded image object
    
    Example:
        - Upload primary image: upload_listing_image(listing_id=123, image_path="/path/to/image.jpg", rank=1)
    """
    if etsy_client is None:
        return {
            "success": False,
            "error": "Not connected to Etsy. Please use connect_etsy tool first."
        }
    
    try:
        from pathlib import Path
        
        # Validate image path
        if not Path(image_path).exists():
            return {
                "success": False,
                "error": f"Image file not found: {image_path}"
            }
        
        # Validate alt_text length
        if alt_text is not None and len(alt_text) > 500:
            return {
                "success": False,
                "error": "alt_text must be 500 characters or less."
            }
        
        user_data = await etsy_client.get_current_user()
        shop_id = user_data.get("shop_id")
        
        if not shop_id:
            return {
                "success": False,
                "error": "No shop_id found for this user."
            }
        
        image_data = await etsy_client.upload_listing_image(
            str(shop_id),
            str(listing_id),
            image_path=image_path,
            rank=rank,
            overwrite=overwrite,
            is_watermarked=is_watermarked,
            alt_text=alt_text
        )
        
        return {
            "success": True,
            "message": f"Successfully uploaded image to listing {listing_id}",
            "image": image_data
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"Error uploading listing image: {str(e)}"
        }


@mcp.tool()
async def delete_listing_image(
    listing_id: int,
    listing_image_id: int
) -> dict:
    """
    Delete an image from a listing.
    
    Note: The file remains on Etsy's servers and can be re-associated with the listing 
    without re-uploading using the upload_listing_image tool with listing_image_id parameter.
    
    Args:
        listing_id: The numeric ID of the listing
        listing_image_id: The numeric ID of the image to delete
    
    Returns:
        Dictionary containing:
        - success: Whether deletion was successful
        - message: Confirmation message
    
    Example:
        - Delete image: delete_listing_image(listing_id=123, listing_image_id=456)
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
        
        await etsy_client.delete_listing_image(
            str(shop_id),
            str(listing_id),
            str(listing_image_id)
        )
        
        return {
            "success": True,
            "message": f"Successfully deleted image {listing_image_id} from listing {listing_id}"
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"Error deleting listing image: {str(e)}"
        }


@mcp.tool()
async def update_variation_images(
    listing_id: int,
    variation_images: list
) -> dict:
    """
    Map specific images to product variations (e.g., blue product shows blue image).
    
    The variation_images array overwrites all existing variation images on the listing.
    Each mapping object should have: property_id, value_id, and image_id.
    
    Args:
        listing_id: The numeric ID of the listing
        variation_images: Array of mapping objects, each with:
                         - property_id: The property ID (e.g., color property)
                         - value_id: The specific value ID (e.g., "blue")
                         - image_id: The image ID to show for this variation
    
    Returns:
        Dictionary containing:
        - success: Whether update was successful
        - message: Confirmation message
        - variation_images: Updated variation images
    
    Example:
        - Map color variations: update_variation_images(
            listing_id=123,
            variation_images=[
                {"property_id": 200, "value_id": 1, "image_id": 100},
                {"property_id": 200, "value_id": 2, "image_id": 101}
            ]
          )
    """
    if etsy_client is None:
        return {
            "success": False,
            "error": "Not connected to Etsy. Please use connect_etsy tool first."
        }
    
    try:
        # Validate variation_images structure
        if not variation_images or not isinstance(variation_images, list):
            return {
                "success": False,
                "error": "variation_images must be a non-empty array."
            }
        
        for mapping in variation_images:
            if not all(k in mapping for k in ["property_id", "value_id", "image_id"]):
                return {
                    "success": False,
                    "error": "Each variation image mapping must have property_id, value_id, and image_id."
                }
        
        user_data = await etsy_client.get_current_user()
        shop_id = user_data.get("shop_id")
        
        if not shop_id:
            return {
                "success": False,
                "error": "No shop_id found for this user."
            }
        
        result_data = await etsy_client.update_variation_images(
            str(shop_id),
            str(listing_id),
            variation_images=variation_images
        )
        
        return {
            "success": True,
            "message": f"Successfully updated variation images for listing {listing_id}",
            "variation_images": result_data
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"Error updating variation images: {str(e)}"
        }


# Inventory Update Tools

@mcp.tool()
async def update_listing_inventory(
    listing_id: int,
    products: list,
    price_on_property: list = None,
    quantity_on_property: list = None,
    sku_on_property: list = None
) -> dict:
    """
    Update inventory for a listing (quantities, prices, SKUs for variants).
    
    This is a complex operation that updates the entire inventory structure.
    The products array must include all products/variants for the listing.
    
    Args:
        listing_id: The numeric ID of the listing
        products: Array of product objects with property_values and offerings
        price_on_property: Array of property IDs that affect pricing
        quantity_on_property: Array of property IDs that affect quantity
        sku_on_property: Array of property IDs that affect SKU
    
    Returns:
        Dictionary containing:
        - success: Whether update was successful
        - message: Confirmation message
        - inventory: Updated inventory object
    
    Example:
        - Update single product inventory: update_listing_inventory(
            listing_id=123,
            products=[{
                "product_id": 1,
                "offerings": [{
                    "offering_id": 1,
                    "price": 25.00,
                    "quantity": 10,
                    "is_enabled": True
                }]
            }]
          )
    """
    if etsy_client is None:
        return {
            "success": False,
            "error": "Not connected to Etsy. Please use connect_etsy tool first."
        }
    
    try:
        # Validate products structure
        if not products or not isinstance(products, list):
            return {
                "success": False,
                "error": "products must be a non-empty array."
            }
        
        inventory_data = await etsy_client.update_listing_inventory(
            str(listing_id),
            products=products,
            price_on_property=price_on_property,
            quantity_on_property=quantity_on_property,
            sku_on_property=sku_on_property
        )
        
        return {
            "success": True,
            "message": f"Successfully updated inventory for listing {listing_id}",
            "inventory": inventory_data
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"Error updating listing inventory: {str(e)}"
        }


# Listing File Management Tools (Digital Products)

@mcp.tool()
async def get_listing_files(listing_id: int) -> dict:
    """
    Get all files for a digital listing.
    
    Args:
        listing_id: The numeric ID of the listing
    
    Returns:
        Dictionary containing:
        - success: Whether the request was successful
        - count: Number of files
        - results: Array of file objects
    
    Example:
        - Get files: get_listing_files(listing_id=123456789)
    """
    if etsy_client is None:
        return {
            "success": False,
            "error": "Not connected to Etsy. Please use connect_etsy tool first."
        }
    
    try:
        files_data = await etsy_client.get_listing_files(str(listing_id))
        
        return {
            "success": True,
            "count": files_data.get("count", 0),
            "results": files_data.get("results", [])
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"Error retrieving listing files: {str(e)}"
        }


@mcp.tool()
async def get_listing_file(
    listing_id: int,
    listing_file_id: int
) -> dict:
    """
    Get a single file from a digital listing.
    
    Args:
        listing_id: The numeric ID of the listing
        listing_file_id: The numeric ID of the file
    
    Returns:
        Dictionary containing:
        - success: Whether the request was successful
        - file: File metadata object
    
    Example:
        - Get file: get_listing_file(listing_id=123, listing_file_id=456)
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
        
        file_data = await etsy_client.get_listing_file(
            str(shop_id),
            str(listing_id),
            str(listing_file_id)
        )
        
        return {
            "success": True,
            "file": file_data
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"Error retrieving listing file: {str(e)}"
        }


@mcp.tool()
async def upload_listing_file(
    listing_id: int,
    file_path: str,
    name: str = None,
    rank: int = 1
) -> dict:
    """
    Upload a file to a digital listing.
    
    Args:
        listing_id: The numeric ID of the listing
        file_path: Path to the file to upload
        name: Optional name for the file
        rank: Position in file display (default: 1)
    
    Returns:
        Dictionary containing:
        - success: Whether upload was successful
        - message: Confirmation message
        - file: Uploaded file metadata
    
    Example:
        - Upload file: upload_listing_file(listing_id=123, file_path="/path/to/file.pdf")
    """
    if etsy_client is None:
        return {
            "success": False,
            "error": "Not connected to Etsy. Please use connect_etsy tool first."
        }
    
    try:
        from pathlib import Path
        
        # Validate file path
        if not Path(file_path).exists():
            return {
                "success": False,
                "error": f"File not found: {file_path}"
            }
        
        user_data = await etsy_client.get_current_user()
        shop_id = user_data.get("shop_id")
        
        if not shop_id:
            return {
                "success": False,
                "error": "No shop_id found for this user."
            }
        
        file_data = await etsy_client.upload_listing_file(
            str(shop_id),
            str(listing_id),
            file_path=file_path,
            name=name,
            rank=rank
        )
        
        return {
            "success": True,
            "message": f"Successfully uploaded file to listing {listing_id}",
            "file": file_data
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"Error uploading listing file: {str(e)}"
        }


@mcp.tool()
async def delete_listing_file(
    listing_id: int,
    listing_file_id: int
) -> dict:
    """
    Delete a file from a digital listing.
    
    Args:
        listing_id: The numeric ID of the listing
        listing_file_id: The numeric ID of the file to delete
    
    Returns:
        Dictionary containing:
        - success: Whether deletion was successful
        - message: Confirmation message
    
    Example:
        - Delete file: delete_listing_file(listing_id=123, listing_file_id=456)
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
        
        await etsy_client.delete_listing_file(
            str(shop_id),
            str(listing_id),
            str(listing_file_id)
        )
        
        return {
            "success": True,
            "message": f"Successfully deleted file {listing_file_id} from listing {listing_id}"
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"Error deleting listing file: {str(e)}"
        }


# Listing Video Management Tools

@mcp.tool()
async def get_listing_videos(listing_id: int) -> dict:
    """
    Get all videos for a listing.
    
    Args:
        listing_id: The numeric ID of the listing
    
    Returns:
        Dictionary containing:
        - success: Whether the request was successful
        - count: Number of videos
        - results: Array of video objects
    
    Example:
        - Get videos: get_listing_videos(listing_id=123456789)
    """
    if etsy_client is None:
        return {
            "success": False,
            "error": "Not connected to Etsy. Please use connect_etsy tool first."
        }
    
    try:
        videos_data = await etsy_client.get_listing_videos(str(listing_id))
        
        return {
            "success": True,
            "count": videos_data.get("count", 0),
            "results": videos_data.get("results", [])
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"Error retrieving listing videos: {str(e)}"
        }


@mcp.tool()
async def get_listing_video(
    listing_id: int,
    video_id: int
) -> dict:
    """
    Get a single video from a listing.
    
    Args:
        listing_id: The numeric ID of the listing
        video_id: The numeric ID of the video
    
    Returns:
        Dictionary containing:
        - success: Whether the request was successful
        - video: Video metadata object
    
    Example:
        - Get video: get_listing_video(listing_id=123, video_id=456)
    """
    if etsy_client is None:
        return {
            "success": False,
            "error": "Not connected to Etsy. Please use connect_etsy tool first."
        }
    
    try:
        video_data = await etsy_client.get_listing_video(
            str(listing_id),
            str(video_id)
        )
        
        return {
            "success": True,
            "video": video_data
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"Error retrieving listing video: {str(e)}"
        }


@mcp.tool()
async def upload_listing_video(
    listing_id: int,
    video_path: str,
    name: str = None
) -> dict:
    """
    Upload a video to a listing.
    
    Args:
        listing_id: The numeric ID of the listing
        video_path: Path to the video file to upload
        name: Optional name for the video
    
    Returns:
        Dictionary containing:
        - success: Whether upload was successful
        - message: Confirmation message
        - video: Uploaded video metadata
    
    Example:
        - Upload video: upload_listing_video(listing_id=123, video_path="/path/to/video.mp4")
    """
    if etsy_client is None:
        return {
            "success": False,
            "error": "Not connected to Etsy. Please use connect_etsy tool first."
        }
    
    try:
        from pathlib import Path
        
        # Validate video path
        if not Path(video_path).exists():
            return {
                "success": False,
                "error": f"Video file not found: {video_path}"
            }
        
        user_data = await etsy_client.get_current_user()
        shop_id = user_data.get("shop_id")
        
        if not shop_id:
            return {
                "success": False,
                "error": "No shop_id found for this user."
            }
        
        video_data = await etsy_client.upload_listing_video(
            str(shop_id),
            str(listing_id),
            video_path=video_path,
            name=name
        )
        
        return {
            "success": True,
            "message": f"Successfully uploaded video to listing {listing_id}",
            "video": video_data
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"Error uploading listing video: {str(e)}"
        }


@mcp.tool()
async def delete_listing_video(
    listing_id: int,
    video_id: int
) -> dict:
    """
    Delete a video from a listing.
    
    Args:
        listing_id: The numeric ID of the listing
        video_id: The numeric ID of the video to delete
    
    Returns:
        Dictionary containing:
        - success: Whether deletion was successful
        - message: Confirmation message
    
    Example:
        - Delete video: delete_listing_video(listing_id=123, video_id=456)
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
        
        await etsy_client.delete_listing_video(
            str(shop_id),
            str(listing_id),
            str(video_id)
        )
        
        return {
            "success": True,
            "message": f"Successfully deleted video {video_id} from listing {listing_id}"
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"Error deleting listing video: {str(e)}"
        }


# Listing Translation Management Tools

@mcp.tool()
async def create_listing_translation(
    listing_id: int,
    language: str,
    title: str,
    description: str,
    tags: list = None
) -> dict:
    """
    Create a translation for a listing.
    
    Args:
        listing_id: The numeric ID of the listing
        language: IETF language tag (e.g., 'de', 'es', 'fr', 'it', 'ja', 'nl', 'pl', 'pt')
        title: Translated listing title
        description: Translated listing description
        tags: Optional array of translated tag strings
    
    Returns:
        Dictionary containing:
        - success: Whether creation was successful
        - message: Confirmation message
        - translation: Created translation object
    
    Example:
        - Create translation: create_listing_translation(listing_id=123, language="es", 
                              title="Taza de cerámica", description="Hermosa taza artesanal")
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
        
        translation_data = await etsy_client.create_listing_translation(
            str(shop_id),
            str(listing_id),
            language=language,
            title=title,
            description=description,
            tags=tags
        )
        
        return {
            "success": True,
            "message": f"Successfully created {language} translation for listing {listing_id}",
            "translation": translation_data
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"Error creating listing translation: {str(e)}"
        }


@mcp.tool()
async def get_listing_translation(
    listing_id: int,
    language: str
) -> dict:
    """
    Get a translation for a listing.
    
    Args:
        listing_id: The numeric ID of the listing
        language: IETF language tag (e.g., 'de', 'es', 'fr', 'it', 'ja', 'nl', 'pl', 'pt')
    
    Returns:
        Dictionary containing:
        - success: Whether the request was successful
        - translation: Translation object with title, description, tags
    
    Example:
        - Get translation: get_listing_translation(listing_id=123, language="es")
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
        
        translation_data = await etsy_client.get_listing_translation(
            str(shop_id),
            str(listing_id),
            language=language
        )
        
        return {
            "success": True,
            "translation": translation_data
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"Error retrieving listing translation: {str(e)}"
        }


@mcp.tool()
async def update_listing_translation(
    listing_id: int,
    language: str,
    title: str,
    description: str,
    tags: list = None
) -> dict:
    """
    Update a translation for a listing.
    
    Args:
        listing_id: The numeric ID of the listing
        language: IETF language tag (e.g., 'de', 'es', 'fr', 'it', 'ja', 'nl', 'pl', 'pt')
        title: Translated listing title
        description: Translated listing description
        tags: Optional array of translated tag strings
    
    Returns:
        Dictionary containing:
        - success: Whether update was successful
        - message: Confirmation message
        - translation: Updated translation object
    
    Example:
        - Update translation: update_listing_translation(listing_id=123, language="es",
                              title="Taza de cerámica hecha a mano", description="...")
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
        
        translation_data = await etsy_client.update_listing_translation(
            str(shop_id),
            str(listing_id),
            language=language,
            title=title,
            description=description,
            tags=tags
        )
        
        return {
            "success": True,
            "message": f"Successfully updated {language} translation for listing {listing_id}",
            "translation": translation_data
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"Error updating listing translation: {str(e)}"
        }


# Taxonomy & Categories Tools

@mcp.tool()
async def get_buyer_taxonomy() -> dict:
    """
    Get the full buyer taxonomy tree (categories).
    
    Returns:
        Dictionary containing:
        - success: Whether the request was successful
        - results: Array of taxonomy node objects
    
    Example:
        - Get taxonomy: get_buyer_taxonomy()
    """
    if etsy_client is None:
        return {
            "success": False,
            "error": "Not connected to Etsy. Please use connect_etsy tool first."
        }
    
    try:
        taxonomy_data = await etsy_client.get_buyer_taxonomy()
        
        return {
            "success": True,
            "results": taxonomy_data.get("results", [])
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"Error retrieving buyer taxonomy: {str(e)}"
        }


@mcp.tool()
async def get_buyer_taxonomy_properties(taxonomy_id: int) -> dict:
    """
    Get properties for a buyer taxonomy category.
    
    Args:
        taxonomy_id: The numeric taxonomy ID
    
    Returns:
        Dictionary containing:
        - success: Whether the request was successful
        - results: Array of property objects with scales and values
    
    Example:
        - Get properties: get_buyer_taxonomy_properties(taxonomy_id=1429)
    """
    if etsy_client is None:
        return {
            "success": False,
            "error": "Not connected to Etsy. Please use connect_etsy tool first."
        }
    
    try:
        properties_data = await etsy_client.get_buyer_taxonomy_properties(str(taxonomy_id))
        
        return {
            "success": True,
            "results": properties_data.get("results", [])
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"Error retrieving buyer taxonomy properties: {str(e)}"
        }


@mcp.tool()
async def get_seller_taxonomy() -> dict:
    """
    Get the full seller taxonomy tree (categories).
    
    Returns:
        Dictionary containing:
        - success: Whether the request was successful
        - results: Array of taxonomy node objects
    
    Example:
        - Get taxonomy: get_seller_taxonomy()
    """
    if etsy_client is None:
        return {
            "success": False,
            "error": "Not connected to Etsy. Please use connect_etsy tool first."
        }
    
    try:
        taxonomy_data = await etsy_client.get_seller_taxonomy()
        
        return {
            "success": True,
            "results": taxonomy_data.get("results", [])
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"Error retrieving seller taxonomy: {str(e)}"
        }


@mcp.tool()
async def get_seller_taxonomy_properties(taxonomy_id: int) -> dict:
    """
    Get properties for a seller taxonomy category.
    
    Args:
        taxonomy_id: The numeric taxonomy ID
    
    Returns:
        Dictionary containing:
        - success: Whether the request was successful
        - results: Array of property objects with scales and values
    
    Example:
        - Get properties: get_seller_taxonomy_properties(taxonomy_id=1429)
    """
    if etsy_client is None:
        return {
            "success": False,
            "error": "Not connected to Etsy. Please use connect_etsy tool first."
        }
    
    try:
        properties_data = await etsy_client.get_seller_taxonomy_properties(str(taxonomy_id))
        
        return {
            "success": True,
            "results": properties_data.get("results", [])
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"Error retrieving seller taxonomy properties: {str(e)}"
        }


# Featured Listings Tools

@mcp.tool()
async def get_featured_listings(
    limit: int = 25,
    offset: int = 0
) -> dict:
    """
    Get featured listings for your shop.
    
    Args:
        limit: Number of results to return (1-100). Default is 25.
        offset: Offset for pagination. Default is 0.
    
    Returns:
        Dictionary containing:
        - success: Whether the request was successful
        - count: Number of featured listings
        - results: Array of listing objects
    
    Example:
        - Get featured listings: get_featured_listings()
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
        
        # Validate limit
        if limit < 1 or limit > 100:
            return {
                "success": False,
                "error": "Limit must be between 1 and 100."
            }
        
        featured_data = await etsy_client.get_featured_listings(
            str(shop_id),
            limit=limit,
            offset=offset
        )
        
        return {
            "success": True,
            "count": featured_data.get("count", 0),
            "results": featured_data.get("results", [])
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"Error retrieving featured listings: {str(e)}"
        }


# Production Partners Tools

@mcp.tool()
async def get_production_partners() -> dict:
    """
    Get production partners for your shop.
    
    Returns:
        Dictionary containing:
        - success: Whether the request was successful
        - count: Number of production partners
        - results: Array of production partner objects
    
    Example:
        - Get partners: get_production_partners()
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
        
        partners_data = await etsy_client.get_production_partners(str(shop_id))
        
        return {
            "success": True,
            "count": partners_data.get("count", 0),
            "results": partners_data.get("results", [])
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"Error retrieving production partners: {str(e)}"
        }


# User Address Management Tools

@mcp.tool()
async def get_user_addresses(
    limit: int = 25,
    offset: int = 0
) -> dict:
    """
    Get all user addresses.
    
    Args:
        limit: Number of results to return (1-100). Default is 25.
        offset: Offset for pagination. Default is 0.
    
    Returns:
        Dictionary containing:
        - success: Whether the request was successful
        - count: Number of addresses
        - results: Array of address objects
    
    Example:
        - Get addresses: get_user_addresses()
    """
    if etsy_client is None:
        return {
            "success": False,
            "error": "Not connected to Etsy. Please use connect_etsy tool first."
        }
    
    try:
        # Validate limit
        if limit < 1 or limit > 100:
            return {
                "success": False,
                "error": "Limit must be between 1 and 100."
            }
        
        addresses_data = await etsy_client.get_user_addresses(
            limit=limit,
            offset=offset
        )
        
        return {
            "success": True,
            "count": addresses_data.get("count", 0),
            "results": addresses_data.get("results", [])
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"Error retrieving user addresses: {str(e)}"
        }


@mcp.tool()
async def get_user_address(user_address_id: int) -> dict:
    """
    Get a single user address by ID.
    
    Args:
        user_address_id: The numeric ID of the address
    
    Returns:
        Dictionary containing:
        - success: Whether the request was successful
        - address: Address object with details
    
    Example:
        - Get address: get_user_address(user_address_id=123)
    """
    if etsy_client is None:
        return {
            "success": False,
            "error": "Not connected to Etsy. Please use connect_etsy tool first."
        }
    
    try:
        address_data = await etsy_client.get_user_address(str(user_address_id))
        
        return {
            "success": True,
            "address": address_data
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"Error retrieving user address: {str(e)}"
        }


@mcp.tool()
async def delete_user_address(user_address_id: int) -> dict:
    """
    Delete a user address.
    
    Args:
        user_address_id: The numeric ID of the address to delete
    
    Returns:
        Dictionary containing:
        - success: Whether deletion was successful
        - message: Confirmation message
    
    Example:
        - Delete address: delete_user_address(user_address_id=123)
    """
    if etsy_client is None:
        return {
            "success": False,
            "error": "Not connected to Etsy. Please use connect_etsy tool first."
        }
    
    try:
        await etsy_client.delete_user_address(str(user_address_id))
        
        return {
            "success": True,
            "message": f"Successfully deleted user address {user_address_id}"
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"Error deleting user address: {str(e)}"
        }


if __name__ == "__main__":
    # Run the MCP server
    mcp.run()

