import time
from typing import Dict, Any, List, Optional
from backend.mcp_server.tools.location import verify_location, reverse_geocode
from backend.mcp_server.tools.drivers import (
    check_driver_availability,
    assign_driver,
    reassign_driver,
)
from backend.mcp_server.tools.fare import calculate_fare
from backend.mcp_server.tools.notifications import notify_user_and_driver

# In-memory execution log for MCP tools (for real-time inspection in frontend)
MCP_EXECUTION_LOG: List[Dict[str, Any]] = []

TOOL_DEFINITIONS = [
    {
        "name": "reverse_geocode",
        "description": "Converts geographic GPS coordinates (latitude and longitude) into a verified physical street address and landmark.",
        "parameters": {
            "type": "object",
            "properties": {
                "lat": {
                    "type": "number",
                    "description": "Latitude coordinate.",
                },
                "lng": {
                    "type": "number",
                    "description": "Longitude coordinate.",
                },
            },
            "required": ["lat", "lng"],
        },
    },
    {
        "name": "verify_location",
        "description": "Verifies whether a pickup or destination address is reachable within the service area and resolves it to geographic coordinates (lat/lng). Must be called before checking drivers or calculating fares.",
        "parameters": {
            "type": "object",
            "properties": {
                "address": {
                    "type": "string",
                    "description": "The street address, landmark, or location name provided by the user.",
                },
                "location_type": {
                    "type": "string",
                    "enum": ["pickup", "destination"],
                    "description": "Whether this address is for 'pickup' or 'destination'.",
                },
            },
            "required": ["address"],
        },
    },
    {
        "name": "check_driver_availability",
        "description": "Queries available drivers filtered by vehicle type (car, bike, or auto) and calculates the nearest available driver to the pickup coordinates. Can also check and book a specific driver if driver_id or driver_name is provided.",
        "parameters": {
            "type": "object",
            "properties": {
                "vehicle_type": {
                    "type": "string",
                    "enum": ["car", "bike", "auto"],
                    "description": "The requested vehicle category.",
                },
                "pickup_lat": {
                    "type": "number",
                    "description": "Latitude of the pickup location.",
                },
                "pickup_lng": {
                    "type": "number",
                    "description": "Longitude of the pickup location.",
                },
                "driver_id": {
                    "type": "integer",
                    "description": "Optional driver ID if a specific driver was requested or previously matched.",
                },
                "driver_name": {
                    "type": "string",
                    "description": "Optional driver name if the rider specifically asked for a named driver.",
                },
                "exclude_driver_ids": {
                    "type": "array",
                    "items": {"type": "integer"},
                    "description": "List of driver IDs to exclude (e.g. if a driver was rejected or reassigned).",
                },
            },
            "required": ["vehicle_type", "pickup_lat", "pickup_lng"],
        },
    },
    {
        "name": "calculate_fare",
        "description": "Calculates the road distance in kilometers and estimated fare in INR based on pickup/destination coordinates and selected vehicle type.",
        "parameters": {
            "type": "object",
            "properties": {
                "pickup_lat": {
                    "type": "number",
                    "description": "Pickup latitude.",
                },
                "pickup_lng": {
                    "type": "number",
                    "description": "Pickup longitude.",
                },
                "destination_lat": {
                    "type": "number",
                    "description": "Destination latitude.",
                },
                "destination_lng": {
                    "type": "number",
                    "description": "Destination longitude.",
                },
                "vehicle_type": {
                    "type": "string",
                    "enum": ["car", "bike", "auto"],
                    "description": "Vehicle type chosen for travel.",
                },
            },
            "required": [
                "pickup_lat",
                "pickup_lng",
                "destination_lat",
                "destination_lng",
                "vehicle_type",
            ],
        },
    },
    {
        "name": "assign_driver",
        "description": "Locks and assigns an available driver to a ride record, transitioning driver status to 'on_trip' and ride status to 'confirmed'.",
        "parameters": {
            "type": "object",
            "properties": {
                "ride_id": {
                    "type": "integer",
                    "description": "The ID of the ride to confirm.",
                },
                "driver_id": {
                    "type": "integer",
                    "description": "The ID of the driver being assigned.",
                },
            },
            "required": ["ride_id", "driver_id"],
        },
    },
    {
        "name": "reassign_driver",
        "description": "Attempts reassignment to the next available driver if the selected driver rejects or is unavailable, with an automatic retry cap.",
        "parameters": {
            "type": "object",
            "properties": {
                "ride_id": {
                    "type": "integer",
                    "description": "The ID of the ride needing reassignment.",
                },
                "rejected_driver_id": {
                    "type": "integer",
                    "description": "The ID of the driver that rejected or could not take the ride.",
                },
            },
            "required": ["ride_id", "rejected_driver_id"],
        },
    },
    {
        "name": "notify_user_and_driver",
        "description": "Sends push notifications and status alerts to both the passenger and assigned driver via Firebase Cloud Messaging.",
        "parameters": {
            "type": "object",
            "properties": {
                "employee_id": {
                    "type": "integer",
                    "description": "The ID of the employee booking the ride.",
                },
                "driver_id": {
                    "type": "integer",
                    "description": "The ID of the assigned driver.",
                },
                "ride_id": {
                    "type": "integer",
                    "description": "The ID of the confirmed ride.",
                },
            },
            "required": ["employee_id", "driver_id", "ride_id"],
        },
    },
]

class MCPServer:
    """Custom Model Context Protocol (MCP) Server for Ride Booking Tools."""

    def __init__(self):
        self.tools = {
            "reverse_geocode": reverse_geocode,
            "verify_location": verify_location,
            "check_driver_availability": check_driver_availability,
            "calculate_fare": calculate_fare,
            "assign_driver": assign_driver,
            "reassign_driver": reassign_driver,
            "notify_user_and_driver": notify_user_and_driver,
        }

    def get_tool_definitions(self) -> List[Dict[str, Any]]:
        """Returns tool definitions formatted for OpenAI Function/Tool calling or MCP clients."""
        return TOOL_DEFINITIONS

    def execute_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Executes the requested tool and records invocation metrics."""
        if tool_name not in self.tools:
            return {
                "error": f"Tool '{tool_name}' not found on MCP Server. Available tools: {list(self.tools.keys())}"
            }

        start_time = time.time()
        func = self.tools[tool_name]

        try:
            result = func(**arguments)
            execution_time_ms = round((time.time() - start_time) * 1000, 2)
            log_entry = {
                "timestamp": time.time(),
                "tool_name": tool_name,
                "arguments": arguments,
                "result": result,
                "latency_ms": execution_time_ms,
                "status": "success",
            }
            MCP_EXECUTION_LOG.append(log_entry)
            if len(MCP_EXECUTION_LOG) > 100:
                MCP_EXECUTION_LOG.pop(0)

            return result
        except Exception as exc:
            execution_time_ms = round((time.time() - start_time) * 1000, 2)
            log_entry = {
                "timestamp": time.time(),
                "tool_name": tool_name,
                "arguments": arguments,
                "error": str(exc),
                "latency_ms": execution_time_ms,
                "status": "error",
            }
            MCP_EXECUTION_LOG.append(log_entry)
            return {"error": f"Error executing tool '{tool_name}': {str(exc)}"}

mcp_server = MCPServer()
