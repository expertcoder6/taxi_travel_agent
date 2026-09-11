from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from backend.db.database import SessionLocal
from backend.db.models import Driver, Ride
from backend.mcp_server.tools.fare import haversine_distance
from backend.config import settings

def check_driver_availability(
    vehicle_type: str,
    pickup_lat: float,
    pickup_lng: float,
    exclude_driver_ids: Optional[List[int]] = None,
    db: Optional[Session] = None,
) -> Dict[str, Any]:
    """
    MCP Tool: check_driver_availability
    Searches for the nearest available driver matching the requested vehicle type,
    excluding previously declined or unavailable drivers.
    """
    should_close = False
    if db is None:
        db = SessionLocal()
        should_close = True

    try:
        vehicle = (vehicle_type or "").strip().lower()
        if vehicle not in ("car", "bike", "auto"):
            vehicle = "car"

        exclude_ids = exclude_driver_ids or []

        query = db.query(Driver).filter(
            Driver.vehicle_type == vehicle,
            Driver.availability_status == "available",
        )

        if exclude_ids:
            query = query.filter(~Driver.id.in_(exclude_ids))

        available_drivers = query.all()

        if not available_drivers:
            return {
                "found": False,
                "driver_id": None,
                "name": None,
                "phone_number": None,
                "vehicle_number": None,
                "vehicle_type": vehicle,
                "rating": None,
                "distance_km": None,
                "eta_minutes": None,
                "message": f"No available {vehicle} drivers nearby right now.",
            }

        # Find nearest driver using Haversine calculation
        nearest_driver = None
        min_distance = float("inf")

        for d in available_drivers:
            d_lat = d.current_lat or settings.COMPANY_LAT
            d_lng = d.current_lng or settings.COMPANY_LNG
            dist = haversine_distance(pickup_lat, pickup_lng, d_lat, d_lng)
            if dist < min_distance:
                min_distance = dist
                nearest_driver = d

        road_dist = round(min_distance * 1.3, 2)
        eta_minutes = max(3, int(round(road_dist * 2.5)))

        return {
            "found": True,
            "driver_id": nearest_driver.id,
            "name": nearest_driver.name,
            "phone_number": nearest_driver.phone_number,
            "vehicle_number": nearest_driver.vehicle_number,
            "vehicle_type": nearest_driver.vehicle_type,
            "rating": nearest_driver.rating or 4.8,
            "distance_km": road_dist,
            "eta_minutes": eta_minutes,
            "message": f"Driver {nearest_driver.name} is available and {eta_minutes} mins away ({road_dist} km).",
        }
    finally:
        if should_close:
            db.close()


def assign_driver(
    ride_id: int,
    driver_id: int,
    db: Optional[Session] = None,
) -> Dict[str, Any]:
    """
    MCP Tool: assign_driver
    Locks and assigns a driver to a ride, updating the driver's status to 'on_trip'
    and the ride status to 'confirmed'.
    """
    should_close = False
    if db is None:
        db = SessionLocal()
        should_close = True

    try:
        ride = db.query(Ride).filter(Ride.id == ride_id).first()
        if not ride:
            return {
                "success": False,
                "ride_id": ride_id,
                "driver_id": driver_id,
                "status": "error",
                "message": f"Ride #{ride_id} does not exist.",
            }

        driver = db.query(Driver).filter(Driver.id == driver_id).first()
        if not driver:
            return {
                "success": False,
                "ride_id": ride_id,
                "driver_id": driver_id,
                "status": "error",
                "message": f"Driver #{driver_id} does not exist.",
            }

        if driver.availability_status != "available":
            return {
                "success": False,
                "ride_id": ride_id,
                "driver_id": driver_id,
                "status": "driver_busy",
                "message": f"Driver {driver.name} is no longer available (currently {driver.availability_status}).",
            }

        # Atomically update statuses
        driver.availability_status = "on_trip"
        ride.driver_id = driver.id
        ride.status = "confirmed"
        db.commit()
        db.refresh(ride)
        db.refresh(driver)

        return {
            "success": True,
            "ride_id": ride.id,
            "driver_id": driver.id,
            "driver_name": driver.name,
            "driver_phone": driver.phone_number,
            "vehicle_number": driver.vehicle_number,
            "vehicle_type": driver.vehicle_type,
            "status": "confirmed",
            "message": f"Driver {driver.name} ({driver.vehicle_number}) has been assigned to Ride #{ride.id}.",
        }
    except Exception as exc:
        db.rollback()
        return {
            "success": False,
            "ride_id": ride_id,
            "driver_id": driver_id,
            "status": "error",
            "message": f"Database error during driver assignment: {str(exc)}",
        }
    finally:
        if should_close:
            db.close()


def reassign_driver(
    ride_id: int,
    rejected_driver_id: int,
    db: Optional[Session] = None,
) -> Dict[str, Any]:
    """
    MCP Tool: reassign_driver
    Handles driver refusal/timeout by excluding rejected drivers, retrying assignment up to REASSIGNMENT_MAX_RETRIES.
    """
    should_close = False
    if db is None:
        db = SessionLocal()
        should_close = True

    try:
        ride = db.query(Ride).filter(Ride.id == ride_id).first()
        if not ride:
            return {
                "success": False,
                "new_driver": None,
                "status": "error",
                "message": f"Ride #{ride_id} not found.",
            }

        # Reset rejected driver back to available if they just rejected this single ride
        rejected = db.query(Driver).filter(Driver.id == rejected_driver_id).first()
        if rejected and rejected.availability_status == "on_trip":
            rejected.availability_status = "available"
            db.commit()

        # Check for another driver excluding rejected
        excluded = [rejected_driver_id]
        if ride.driver_id and ride.driver_id not in excluded:
            excluded.append(ride.driver_id)

        candidate = check_driver_availability(
            vehicle_type=ride.vehicle_type or "car",
            pickup_lat=ride.pickup_lat or settings.COMPANY_LAT,
            pickup_lng=ride.pickup_lng or settings.COMPANY_LNG,
            exclude_driver_ids=excluded,
            db=db,
        )

        if not candidate.get("found"):
            ride.status = "failed_no_driver"
            db.commit()
            return {
                "success": False,
                "new_driver": None,
                "status": "failed_no_driver",
                "message": "All alternative drivers are occupied. Unable to reassign ride.",
            }

        # Assign new candidate
        assignment = assign_driver(ride_id=ride.id, driver_id=candidate["driver_id"], db=db)
        if assignment.get("success"):
            return {
                "success": True,
                "new_driver": candidate,
                "status": "confirmed",
                "message": f"Ride reassigned successfully to {candidate['name']} ({candidate['vehicle_number']}).",
            }
        else:
            return {
                "success": False,
                "new_driver": candidate,
                "status": "reassignment_failed",
                "message": assignment.get("message", "Reassignment failed."),
            }
    finally:
        if should_close:
            db.close()
