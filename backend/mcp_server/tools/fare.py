import math
from typing import Dict, Any
from backend.config import settings

EARTH_RADIUS_KM = 6371.0
ROAD_CURVATURE_FACTOR = 1.3

def haversine_distance(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Computes great-circle distance between two geographic points in kilometers."""
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lng2 - lng1)

    a = (
        math.sin(delta_phi / 2.0) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2.0) ** 2
    )
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return EARTH_RADIUS_KM * c

def calculate_fare(
    pickup_lat: float,
    pickup_lng: float,
    destination_lat: float,
    destination_lng: float,
    vehicle_type: str,
) -> Dict[str, Any]:
    """
    MCP Tool: calculate_fare
    Calculates distance and estimated fare based on vehicle type and road curvature.
    """
    vehicle = (vehicle_type or "").strip().lower()
    if vehicle not in settings.FARE_RATES:
        vehicle = "car"  # Default fallback if unknown

    rates = settings.FARE_RATES[vehicle]

    straight_dist = haversine_distance(pickup_lat, pickup_lng, destination_lat, destination_lng)
    # Factor in road turns, traffic detours, and metro street network
    road_distance = max(1.0, round(straight_dist * ROAD_CURVATURE_FACTOR, 2))

    base_fare = rates["base_fare"]
    rate_per_km = rates["rate_per_km"]
    min_fare = rates["min_fare"]

    computed_fare = round(base_fare + (road_distance * rate_per_km), 2)
    final_fare = max(computed_fare, min_fare)

    return {
        "distance_km": road_distance,
        "fare": round(final_fare, 2),
        "base_fare": base_fare,
        "rate_per_km": rate_per_km,
        "vehicle_type": vehicle,
        "currency": "INR",
        "currency_symbol": "₹",
    }
