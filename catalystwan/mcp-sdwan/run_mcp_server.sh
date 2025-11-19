#/bin/bash
#
# To quickly test the MCP SD-WAN Server container locally with Podman.
#
# -----------------------------------------------------------------
# # Create podman secrets
# Create secrets for vManage host, port, username and password
# -----------------------------------------------------------------
#
# echo -n "your-vmanage-hostname.com" | podman secret create vmanage_host -
# echo -n "your-vmanage-port" | podman secret create vmanage_port -
# echo -n "your-vmanage-username" | podman secret create vmanage_username -
# echo -n "your-vmanage-password" | podman secret create vmanage_password -
#
# -----------------------------------------------------------------
# Access container as root user for debugging:
# -----------------------------------------------------------------
#
# podman exec -it -u root <CONTAINER_ID> bash
#
# -----------------------------------------------------------------
# Options
# -----------------------------------------------------------------
#
# -d: Runs the container in detached mode (in the background).
#

podman run -i --rm \
  --secret vmanage_host,type=env,target=VMANAGE_HOST \
  --secret vmanage_port,type=env,target=VMANAGE_PORT \
  --secret vmanage_username,type=env,target=VMANAGE_USERNAME \
  --secret vmanage_password,type=env,target=VMANAGE_PASSWORD \
  sdwan-mcp-server:latest
