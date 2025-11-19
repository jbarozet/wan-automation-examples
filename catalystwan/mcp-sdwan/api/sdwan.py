import asyncio
import json
import logging
import os
import sys

import httpx

# Configure logging to stderr
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stderr
)
logger = logging.getLogger("sdwan-mcp-server")

# Configuration
VMANAGE_HOST = os.getenv("VMANAGE_HOST", "https://your-sdwan-instance.cisco.com")
VMANAGE_PORT = os.getenv("VMANAGE_PORT", "443")
VMANAGE_USERNAME = os.getenv("VMANAGE_USERNAME", "admin")
VMANAGE_PASSWORD = os.getenv("VMANAGE_PASSWORD", "your-password")


# === UTILITY FUNCTIONS ===

async def authenticate_vmanage(host: str, port: str, username: str, password: str):
    """Authenticate with vManage and return session token."""
    base_url = f"https://{host}:{port}"

    async with httpx.AsyncClient(verify=False, timeout=30.0, follow_redirects=True) as client:
        try:
            # Step 1: Perform login to get session cookie
            logger.info("Performing initial login...")
            auth_data = {
                "j_username": username,
                "j_password": password
            }

            auth_response = await client.post(
                f"{base_url}/j_security_check",
                data=auth_data,
                headers={"Content-Type": "application/x-www-form-urlencoded"}
            )

            # Check if login was successful
            if auth_response.status_code != 200:
                logger.error(f"Authentication failed with status: {auth_response.status_code}")
                raise Exception(f"Authentication failed: {auth_response.status_code}")

            try:
                response_json = auth_response.json()
                if "error" in response_json and "message" in response_json["error"] and "Login Error" in response_json["error"]["message"]:
                    logger.error(f"Authentication failed: vManage returned login error in JSON response. Details: {response_json['error'].get('details', 'N/A')}")
                    raise Exception(f"Authentication failed: Invalid credentials or access denied (vManage error: {response_json['error'].get('message', 'Unknown')})")
            except json.JSONDecodeError:
                # Not a JSON response, proceed with existing checks
                pass

            # Check if we got redirected back to login (auth failed)
            if "/login" in str(auth_response.url) or "j_security_check" in auth_response.text:
                logger.error(f"Authentication failed: Invalid credentials or access denied. Response URL: {auth_response.url}, Response text snippet: {auth_response.text[:200]}")
                raise Exception("Authentication failed: Invalid credentials or access denied")

            logger.info("Login successful, retrieving CSRF token...")

            # Step 2: Now get the CSRF token with authenticated session
            token_response = await client.get(
                f"{base_url}/dataservice/client/token",
                cookies=auth_response.cookies
            )

            if token_response.status_code != 200:
                logger.error(f"Failed to get CSRF token: {token_response.status_code}")
                raise Exception(f"Failed to get CSRF token: {token_response.status_code}")

            csrf_token = token_response.text.strip()

            # Validate that we got a token, not HTML
            if csrf_token.startswith('<') or len(csrf_token) > 500:
                logger.error(f"Failed to retrieve valid CSRF token - got HTML response instead. Response snippet: {csrf_token[:200]}")
                raise Exception("Failed to retrieve valid CSRF token - got HTML response instead")

            logger.info(f"CSRF token retrieved successfully (length: {len(csrf_token)})")

            return {
                "base_url": base_url,
                "cookies": auth_response.cookies,
                "csrf_token": csrf_token
            }

        except httpx.HTTPError as e:
            logger.error(f"HTTP error during authentication: {e}")
            raise Exception(f"Network error during authentication: {str(e)}")
        except Exception as e:
            logger.error(f"Authentication error: {e}")
            raise

async def make_api_get_data(session: dict, url: str) -> list:
    """
    Make an authenticated GET request to vManage endpoint.
    """

    async with httpx.AsyncClient(verify=False, timeout=30.0, cookies=session["cookies"]) as client:
        headers = {"X-XSRF-TOKEN": session["csrf_token"]}

        response = await client.get(
            f"{session['base_url']}/{url}",
            headers=headers
        )

        if response.status_code != 200:
            raise Exception(f"Failed to get data from {url}: {response.status_code}")

        return response.json().get("data", [])

async def make_api_get(session: dict, url: str) -> list:
    """
    Make an authenticated GET request to vManage endpoint.
    """

    async with httpx.AsyncClient(verify=False, timeout=30.0, cookies=session["cookies"]) as client:
        headers = {"X-XSRF-TOKEN": session["csrf_token"]}

        response = await client.get(
            f"{session['base_url']}/{url}",
            headers=headers
        )

        if response.status_code != 200:
            raise Exception(f"Failed to get data from {url}: {response.status_code}")

        return response.json()



async def make_api_post(session: dict, url: str, payload: dict) -> dict:
    """
    Make an authenticated POST request to a vManage API endpoint.
    """

    async with httpx.AsyncClient(verify=False, timeout=30.0, cookies=session["cookies"]) as client:
        headers = {"X-XSRF-TOKEN": session["csrf_token"]}

        response = await client.post(
            f"{session['base_url']}/{url}",
            headers=headers,
            json=payload
        )

        if response.status_code != 200:
            raise Exception(f"Failed to POST to {url}: {response.status_code} - {response.text}")

        return response.json()


# === API FUNCTIONS ===

async def get_device_list():
    """Get list of all devices from vManage."""

    logger.info("Get list of all devices from vManage")
    logger.info
    # Authenticate with vManage
    logger.info("Authenticating with vManage...")
    session_info = await authenticate_vmanage(VMANAGE_HOST, VMANAGE_PORT, VMANAGE_USERNAME, VMANAGE_PASSWORD)

    # Get device list
    logger.info("Retrieving device list...")
    devices = await make_api_get_data(session=session_info, url="dataservice/device")

    return devices

async def get_device_status():
    """Get device status from vManage."""

    logger.info("Get device status from vManage")

    # Authenticate with vManage
    logger.info("Authenticating with vManage...")
    session_info = await authenticate_vmanage(VMANAGE_HOST, VMANAGE_PORT, VMANAGE_USERNAME, VMANAGE_PASSWORD)

    # Get device list
    logger.info("Retrieving device list...")
    devices = await make_api_get_data(session=session_info, url="dataservice/device/monitor")

    return devices

async def get_approute_stats(rtr1_systemip: str, rtr2_systemip: str):
    """
    Create Average Approute statistics for all tunnels between provided 2 routers for last 1 hour.
    """

    logger.info("Get App Route statistics between two routers")

    # Authenticate with vManage
    logger.info("Authenticating with vManage...")
    session_info = await authenticate_vmanage(VMANAGE_HOST, VMANAGE_PORT, VMANAGE_USERNAME, VMANAGE_PASSWORD)

    # Build query with Routers System IPs

    # Query payloads

    payload_r1_r2 = {
        "query": {
            "condition": "AND",
            "rules": [
                {
                    "value": ["1"],
                    "field": "entry_time",
                    "type": "date",
                    "operator": "last_n_hours",
                },
                {
                    "value": [rtr1_systemip],
                    "field": "local_system_ip",
                    "type": "string",
                    "operator": "in",
                },
                {
                    "value": [rtr2_systemip],
                    "field": "remote_system_ip",
                    "type": "string",
                    "operator": "in",
                },
            ],
        },
        "aggregation": {
            "field": [{"property": "name", "sequence": 1, "size": 6000}],
            "metrics": [
                {"property": "loss_percentage", "type": "avg"},
                {"property": "vqoe_score", "type": "avg"},
                {"property": "latency", "type": "avg"},
                {"property": "jitter", "type": "avg"},
            ],
        },
    }

    payload_r2_r1 = {
        "query": {
            "condition": "AND",
            "rules": [
                {
                    "value": ["1"],
                    "field": "entry_time",
                    "type": "date",
                    "operator": "last_n_hours",
                },
                {
                    "value": [rtr2_systemip],
                    "field": "local_system_ip",
                    "type": "string",
                    "operator": "in",
                },
                {
                    "value": [rtr1_systemip],
                    "field": "remote_system_ip",
                    "type": "string",
                    "operator": "in",
                },
            ],
        },
        "aggregation": {
            "field": [{"property": "name", "sequence": 1, "size": 6000}],
            "metrics": [
                {"property": "loss_percentage", "type": "avg"},
                {"property": "vqoe_score", "type": "avg"},
                {"property": "latency", "type": "avg"},
                {"property": "jitter", "type": "avg"},
            ],
        },
    }

    # Get app route statistics for tunnels from router-1 to router-2
    response1 = await make_api_post(session=session_info, url="dataservice/statistics/approute/aggregation", payload=payload_r1_r2)

    # Get app route statistics for tunnels from router-2 to router-1
    response2 = await make_api_post(session=session_info, url="dataservice/statistics/approute/aggregation", payload=payload_r2_r1)

    return response1, response2

async def get_config_groups_and_profiles():
    """
    Get a list of all configuration groups and their associated device templates (profiles)
    with name and ID from vManage, using the UX 2.0 Configuration API.
    Returns:
        list: A list of dictionaries containing configuration group details and associated profiles.
    """

    logger.info("Retrieving configuration groups and associated profiles from vManage (UX 2.0 API)...")
    session_info = await authenticate_vmanage(VMANAGE_HOST, VMANAGE_PORT, VMANAGE_USERNAME, VMANAGE_PASSWORD)

    # Corrected endpoint based on the provided OpenAPI spec for UX 2.0 Configuration
    groups_data = await make_api_get(session=session_info, url="dataservice/v1/config-group")

    result_groups = []
    if groups_data:
        for group in groups_data:
            # Keys from the provided payload for ConfigGroup object
            group_id = group.get('id', 'N/A')
            group_name = group.get('name', 'N/A')
            group_description = group.get('description', 'No description provided.')
            group_last_updated_on = group.get('lastUpdatedOn', None)

            associated_profiles = []
            profiles_list = group.get('profiles', [])

            for profile_info in profiles_list:
                # Each profile object in the 'profiles' list has 'id' and 'name'.
                profile_id = profile_info.get('id', 'N/A')
                profile_name = profile_info.get('name', 'N/A')
                profile_last_updated_on = profile_info.get('lastUpdatedOn', None)
                associated_profiles.append({"id": profile_id, "name": profile_name, "lastUpdatedOn": profile_last_updated_on})

            result_groups.append({
                "id": group_id,
                "name": group_name,
                "description": group_description,
                "lastUpdatedOn": group_last_updated_on,
                "profiles": associated_profiles
            })
    return result_groups


# === MAIN ===

if __name__ == "__main__":
    devices = asyncio.run(get_device_list())
    print(json.dumps(devices, indent=4))

    groups = asyncio.run(get_config_groups_and_profiles())
    print(json.dumps(groups, indent=4))
