import json
import logging
import os
import sys
import datetime
from collections import defaultdict
from dotenv import load_dotenv

from mcp.server.fastmcp import FastMCP

from api.sdwan import get_approute_stats, get_config_groups_and_profiles, get_device_list, get_device_status

mcp = FastMCP()

# === MCP TOOLS - DEVICE LIST ===

@mcp.tool("get_device_list")
async def get_device_list_tool():
    """
    Get the list of devices from the SD-WAN Manager.

    Retrieves a list of all devices managed by the SD-WAN Manager,
    including their details and configurations.

    Returns:
        JSON array containing device information such as device ID, name,
        status, IP address, and other relevant metadata.
    """
    result = await get_device_list()
    if result:
        return result
    else:
        return {"error": "Failed to retrieve device list"}

@mcp.tool("get_device_status")
async def get_device_status_tool():
    """
    Get the status of devices from the SD-WAN Manager.

    Retrieves the current status of all devices managed by the SD-WAN Manager,
    including their operational state, connectivity status, and health metrics.

    Returns:
        JSON array containing device status information such as device ID,
        status, uptime, and other relevant metrics.
    """
    result = await get_device_status()
    if result:
        return result
    else:
        return {"error": "Failed to retrieve device status"}


# === MCP TOOL - DEVICE DETAILS ===
# Define the tool to get device details

DEVICE_DETAILS_TEMPLATE = """✅ Device Details: {host_name}

📊 **Basic Information:**
- Type: {device_type}
- Model: {device_model}
- Serial: {uuid}
- System IP: {system_ip}

🔧 **Software Information:**
- Version: {version}
- Platform: {platform}

🌐 **Network Status:**
- Reachability: {reachability}
- State: {state}
- Site ID: {site_id}

⏱️ **Uptime:**
- Uptime: {uptime_date}
- Last Updated: {lastupdated}"""

@mcp.tool("get_device_details")
async def get_device_details(device_name: str = "") -> str:
    """
    Get detailed information about a specific device in the SD-WAN network.
    Args:
        device_name (str): The name of the device to retrieve details for.
    Returns:
        str: Formatted string containing device details or an error message.
    """

    logger.info(f"Getting details for device: {device_name}")

    try:
        # Get all devices (assuming get_device_list is defined elsewhere)
        devices = await get_device_list()

        # Find specific device
        target_device = None
        for device in devices:
            if device.get("host-name", "").lower() == device_name.lower():
                target_device = device
                break

        if not target_device:
            return f"❌ Device '{device_name}' not found in the network"

        # Prepare data for the template, providing default values
        details = {
            "host_name": target_device.get('host-name', 'Unknown'),
            "device_type": target_device.get('device-type', 'Unknown'),
            "device_model": target_device.get('device-model', 'Unknown'),
            "uuid": target_device.get('uuid', 'Unknown'),
            "system_ip": target_device.get('system-ip', 'Unknown'),
            "version": target_device.get('version', 'Unknown'),
            "platform": target_device.get('platform', 'Unknown'),
            "reachability": target_device.get('reachability', 'Unknown'),
            "state": target_device.get('state', 'Unknown'),
            "site_id": target_device.get('site-id', 'Unknown'),
            "uptime_date": target_device.get('uptime-date', 'Unknown'),
            "lastupdated": target_device.get('lastupdated', 'Unknown'),
        }

        # Format device details using the constant template
        result = DEVICE_DETAILS_TEMPLATE.format(**details)

        return result

    except Exception as e:
        logger.error(f"Error getting device details: {e}")
        return f"❌ Error: {str(e)}"


# === MCP TOOL - LIST SOFTWARE VERSIONS ===

@mcp.tool("list_software_versions")
async def list_software_versions() -> str:
    """
    List all unique software versions present in the SD-WAN network.
    Returns:
        str: Formatted string listing software versions and associated device types.
    """

    logger.info("Listing all software versions in the network")

    try:
        # Get devices
        devices = await get_device_list()

        if not devices:
            return "⚠️ No devices found in the network"

        # Collect unique versions
        version_info = defaultdict(list)

        for device in devices:
            version = device.get("version", "Unknown")
            device_type = device.get("device-type", "Unknown")
            version_info[version].append(device_type)

        # Format response
        result = "✅ Software Versions in SD-WAN Network\n\n"

        for version in sorted(version_info.keys()):
            device_types = version_info[version]
            type_counts = defaultdict(int)
            for dt in device_types:
                type_counts[dt] += 1

            result += f"📦 **Version: {version}**\n"
            result += f"   Total devices: {len(device_types)}\n"
            for dt, count in type_counts.items():
                result += f"   - {dt}: {count}\n"
            result += "\n"

        result += f"Total unique versions: {len(version_info)}"

        return result

    except Exception as e:
        logger.error(f"Error listing software versions: {e}")
        return f"❌ Error: {str(e)}"

# === MCP TOOL - APP ROUTE STATISTICS ===

@mcp.tool("get_approute_stats")
async def get_approute_stats_tool(rtr1_systemip: str, rtr2_systemip: str):
    """
    Get application route statistics between two routers for the last hour.
    Args:
        rtr1_systemip (str): System IP of the first router.
        rtr2_systemip (str): System IP of the second router.
    Returns:
        dict: A dictionary containing application route statistics for both routers.
    """

    try:
        response1, response2 = await get_approute_stats(rtr1_systemip, rtr2_systemip)
        return {"response1": response1, "response2": response2}

    except Exception as e:
        logger.error(f"Error getting app route stats: {e}")
        return f"❌ Error: {str(e)}"

# === MCP TOOL - LIST CONFIGURATION GROUPS AND PROFILES ===

@mcp.tool("list_config_groups_and_profiles")
async def list_config_groups_and_profiles() -> str:
    """
    List all configuration groups defined in the SD-WAN Manager and their associated device templates (profiles).
    Returns:
        str: Formatted string listing configuration groups, their descriptions, and associated profiles (name, ID, and last updated timestamp).
    """
    logger.info("Listing all configuration groups and associated profiles in the network")

    try:
        groups_info = await get_config_groups_and_profiles() # Call the API function

        if not groups_info:
            return "⚠️ No configuration groups found in the SD-WAN Manager."

        result = "✅ **Cisco Catalyst SD-WAN Configuration Groups and Associated Profiles (UX 2.0)**\n\n"

        for group in groups_info:
            group_name = group.get('name', 'Unknown Group')
            group_id = group.get('id', 'N/A')
            group_last_updated = group.get('lastUpdatedOn', 'N/A')
            group_description = group.get('description', 'No description provided.')
            profiles = group.get('profiles', [])

            result += f"### ⚙️ Group Name: {group_name} (ID: {group_id}, Last updated on: {group_last_updated})\n"
            result += f"Description: {group_description}\n"

            if profiles:
                result += "Associated Profiles:\n"
                for profile in profiles:
                    profile_name = profile.get('name', 'Unknown Profile')
                    profile_id = profile.get('id', 'N/A')
                    last_updated_timestamp = profile.get('lastUpdatedOn')

                    last_updated_str = "N/A"
                    if last_updated_timestamp is not None and isinstance(last_updated_timestamp, (int, float)):
                        try:
                            # Convert milliseconds to seconds
                            dt_object = datetime.datetime.fromtimestamp(last_updated_timestamp / 1000, tz=datetime.timezone.utc)
                            last_updated_str = dt_object.strftime('%Y-%m-%d %H:%M:%S UTC')
                        except Exception as dt_e:
                            logger.warning(f"Could not convert timestamp {last_updated_timestamp}: {dt_e}")
                            last_updated_str = f"Invalid Timestamp ({last_updated_timestamp})"

                    result += f"  - Name: {profile_name} (ID: {profile_id})\n"
                    result += f"    Last Updated: {last_updated_str}\n"
            else:
                result += "  No associated profiles.\n"
            result += "\n" # Add a newline for separation between groups

        return result

    except Exception as e:
        logger.error(f"Error listing configuration groups and profiles: {e}")
        return f"❌ Error: {str(e)}"

# === SERVER STARTUP ===

if __name__ == "__main__":

    # Configure logging to stderr
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        stream=sys.stderr
    )
    logger = logging.getLogger("sdwan-mcp-server")

    logger.info("Starting Cisco Catalyst SD-WAN Software Check MCP server...")

    # Configuration
    VMANAGE_HOST = os.getenv("VMANAGE_HOST", "")
    VMANAGE_PORT = os.getenv("VMANAGE_PORT", "443")
    VMANAGE_USERNAME = os.getenv("VMANAGE_USERNAME", "")
    VMANAGE_PASSWORD = os.getenv("VMANAGE_PASSWORD", "")

    if not VMANAGE_USERNAME:
        logger.warning("VMANAGE_USERNAME not set - will be required for operations")
    if not VMANAGE_PASSWORD:
        logger.warning("VMANAGE_PASSWORD not set - will be required for operations")
    if not VMANAGE_HOST:
        logger.info("VMANAGE_HOST not set - can be provided as parameter to tools")
    if not VMANAGE_PORT:
        logger.info("VMANAGE_PORT not set - can be provided as parameter to tools")

    logger.info(f"VMANAGE_HOST: '{VMANAGE_HOST}'")
    logger.info(f"VMANAGE_PORT: '{VMANAGE_PORT}'")
    logger.info(f"VMANAGE_USERNAME: '{VMANAGE_USERNAME}'")
    logger.info(f"VMANAGE_PASSWORD (length): '{len(VMANAGE_PASSWORD) if VMANAGE_PASSWORD else 0}'") # Don't log password directly

    try:
        mcp.run(transport='stdio')
    except Exception as e:
        logger.error(f"Server error: {e}", exc_info=True)
        sys.exit(1)
