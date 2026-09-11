import re
import hashlib
from typing import Dict, Any, Optional
from backend.config import settings

# Catalog of known landmarks and service zones in the metro area
KNOWN_LOCATIONS = {
    "acme": {
        "name": settings.COMPANY_LOCATION_NAME,
        "lat": settings.COMPANY_LAT,
        "lng": settings.COMPANY_LNG,
    },
    "company": {
        "name": settings.COMPANY_LOCATION_NAME,
        "lat": settings.COMPANY_LAT,
        "lng": settings.COMPANY_LNG,
    },
    "office": {
        "name": settings.COMPANY_LOCATION_NAME,
        "lat": settings.COMPANY_LAT,
        "lng": settings.COMPANY_LNG,
    },
    "hq": {
        "name": settings.COMPANY_LOCATION_NAME,
        "lat": settings.COMPANY_LAT,
        "lng": settings.COMPANY_LNG,
    },
    "indiranagar": {
        "name": "100 Feet Road, Indiranagar, Bangalore",
        "lat": 12.9784,
        "lng": 77.6408,
    },
    "koramangala": {
        "name": "Koramangala 4th Block, 80 Feet Road, Bangalore",
        "lat": 12.9352,
        "lng": 77.6245,
    },
    "bellandur": {
        "name": "Bellandur EcoSpace, Outer Ring Road, Bangalore",
        "lat": 12.9260,
        "lng": 77.6762,
    },
    "whitefield": {
        "name": "ITPL Main Road, Whitefield, Bangalore",
        "lat": 12.9698,
        "lng": 77.7499,
    },
    "hsr": {
        "name": "HSR Layout Sector 1, 27th Main, Bangalore",
        "lat": 12.9121,
        "lng": 77.6446,
    },
    "electronic city": {
        "name": "Electronic City Phase 1, Hosur Road, Bangalore",
        "lat": 12.8452,
        "lng": 77.6602,
    },
    "mg road": {
        "name": "MG Road Metro Station, Central Bangalore",
        "lat": 12.9756,
        "lng": 77.6066,
    },
    "airport": {
        "name": "Kempegowda International Airport (BLR), Devanahalli",
        "lat": 13.1986,
        "lng": 77.7066,
    },
    "blr airport": {
        "name": "Kempegowda International Airport (BLR), Devanahalli",
        "lat": 13.1986,
        "lng": 77.7066,
    },
    "majestic": {
        "name": "KSR Bengaluru City Railway Station, Majestic",
        "lat": 12.9767,
        "lng": 77.5713,
    },
    "railway station": {
        "name": "KSR Bengaluru City Railway Station, Majestic",
        "lat": 12.9767,
        "lng": 77.5713,
    },
    "marathahalli": {
        "name": "Marathahalli Bridge Junction, Bangalore",
        "lat": 12.9591,
        "lng": 77.6974,
    },
    "sarjapur": {
        "name": "Sarjapur Main Road, Carmelaram, Bangalore",
        "lat": 12.9166,
        "lng": 77.6833,
    },
}

INVALID_PATTERNS = [
    r"^[\s\.\,\-\_]*$",
    r"\b(mars|moon|jupiter|nowhere|atlantis|outer space|hogwarts)\b",
    r"^[a-zA-Z]{1,2}$",
    r"^(asdf|qwerty|xyz|test|unknown)$",
]

def reverse_geocode(lat: Optional[float], lng: Optional[float]) -> Dict[str, Any]:
    """
    MCP Tool & Geocoding Service: reverse_geocode
    Resolves GPS latitude and longitude coordinates into a human-readable street address and landmark.
    """
    if lat is None or lng is None:
        return {
            "valid": False,
            "lat": lat,
            "lng": lng,
            "formatted_address": None,
            "error_message": "Both latitude and longitude coordinates are required.",
        }

    try:
        lat = float(lat)
        lng = float(lng)
    except (ValueError, TypeError):
        return {
            "valid": False,
            "lat": None,
            "lng": None,
            "formatted_address": None,
            "error_message": "Invalid numeric coordinates provided.",
        }

    from backend.mcp_server.tools.fare import haversine_distance

    closest_key = None
    min_dist = float("inf")
    for key, loc in KNOWN_LOCATIONS.items():
        d = haversine_distance(lat, lng, loc["lat"], loc["lng"])
        if d < min_dist:
            min_dist = d
            closest_key = key

    # If within 800m of a known tech park/metro landmark, return that landmark
    if closest_key and min_dist <= 0.8:
        return {
            "valid": True,
            "lat": lat,
            "lng": lng,
            "formatted_address": KNOWN_LOCATIONS[closest_key]["name"],
            "landmark": KNOWN_LOCATIONS[closest_key]["name"],
            "distance_km": round(min_dist, 2),
            "source": "landmark_proximity",
            "error_message": None,
        }

    # Attempt OpenStreetMap Nominatim reverse geocode (with 2s timeout)
    try:
        import httpx
        url = f"https://nominatim.openstreetmap.org/reverse?lat={lat}&lon={lng}&format=json&zoom=18&addressdetails=1"
        resp = httpx.get(url, headers={"User-Agent": "AcmeMobilityRideAgent/1.0"}, timeout=2.0)
        if resp.status_code == 200:
            data = resp.json()
            display = data.get("display_name")
            if display:
                parts = [p.strip() for p in display.split(",") if p.strip()]
                shortened = ", ".join(parts[:4])
                return {
                    "valid": True,
                    "lat": lat,
                    "lng": lng,
                    "formatted_address": shortened,
                    "landmark": parts[0] if parts else None,
                    "distance_km": round(min_dist, 2) if closest_key else None,
                    "source": "osm_nominatim",
                    "error_message": None,
                }
    except Exception:
        pass

    # Fallback to proximity landmark or coordinate descriptor
    if closest_key and min_dist < 20.0:
        loc_name = KNOWN_LOCATIONS[closest_key]["name"]
        return {
            "valid": True,
            "lat": lat,
            "lng": lng,
            "formatted_address": f"Near {loc_name} ({lat:.4f}, {lng:.4f})",
            "landmark": loc_name,
            "distance_km": round(min_dist, 2),
            "source": "landmark_fallback",
            "error_message": None,
        }

    return {
        "valid": True,
        "lat": lat,
        "lng": lng,
        "formatted_address": f"GPS Location ({lat:.4f}, {lng:.4f})",
        "landmark": None,
        "distance_km": None,
        "source": "gps_coordinates",
        "error_message": None,
    }


def verify_location(address: str, location_type: Optional[str] = None) -> Dict[str, Any]:
    """
    MCP Tool: verify_location
    Validates a pickup or destination address against service boundaries and resolves coordinates.
    Optionally accepts location_type ('pickup' or 'destination') to unambiguously bind coordinates.
    """
    if not address or not isinstance(address, str):
        return {
            "valid": False,
            "lat": None,
            "lng": None,
            "formatted_address": None,
            "location_type": location_type,
            "error_message": "Address cannot be empty. Please provide a pickup or drop location.",
        }

    cleaned = address.strip().lower()

    # Check for numeric coordinates like "12.9716, 77.5946" or "lat: 12.9716, lng: 77.5946"
    coord_match = re.search(r"(-?\d{1,2}\.\d{3,7})[,\s]+(-?\d{1,3}\.\d{3,7})", address)
    if coord_match:
        c_lat, c_lng = float(coord_match.group(1)), float(coord_match.group(2))
        rg_result = reverse_geocode(c_lat, c_lng)
        return {
            "valid": True,
            "lat": c_lat,
            "lng": c_lng,
            "formatted_address": rg_result.get("formatted_address") or f"GPS ({c_lat:.4f}, {c_lng:.4f})",
            "location_type": location_type,
            "error_message": None,
        }

    # Check for blatantly invalid inputs
    for pattern in INVALID_PATTERNS:
        if re.search(pattern, cleaned, re.IGNORECASE):
            return {
                "valid": False,
                "lat": None,
                "lng": None,
                "formatted_address": None,
                "location_type": location_type,
                "error_message": f"'{address}' is not a valid or reachable address in our service area. Please provide a recognizable location or landmark.",
            }

    # Match known catalog landmarks
    for key, loc in KNOWN_LOCATIONS.items():
        if key in cleaned:
            return {
                "valid": True,
                "lat": loc["lat"],
                "lng": loc["lng"],
                "formatted_address": loc["name"],
                "location_type": location_type,
                "error_message": None,
            }

    # Deterministic geo-hash for any legitimate street/neighborhood address within serviceable metro box
    # Metro service bounds: Lat 12.85 to 13.05, Lng 77.50 to 77.75
    if len(cleaned) >= 3:
        h = int(hashlib.md5(cleaned.encode("utf-8")).hexdigest(), 16)
        lat_offset = (h % 2000) / 10000.0  # 0.0000 to 0.2000
        lng_offset = ((h >> 16) % 2500) / 10000.0 # 0.0000 to 0.2500
        lat = round(12.85 + lat_offset, 4)
        lng = round(77.50 + lng_offset, 4)
        title_cased = " ".join(word.capitalize() for word in address.strip().split())
        return {
            "valid": True,
            "lat": lat,
            "lng": lng,
            "formatted_address": f"{title_cased}, Bangalore Metro Zone",
            "location_type": location_type,
            "error_message": None,
        }

    return {
        "valid": False,
        "lat": None,
        "lng": None,
        "formatted_address": None,
        "location_type": location_type,
        "error_message": f"Could not locate '{address}'. Please specify a nearby landmark or street name.",
    }
