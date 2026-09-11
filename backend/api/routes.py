from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.config import settings
from backend.db.database import get_db
from backend.db.models import Driver, Employee, Ride, ConversationState
from backend.db.seed import seed_database
from backend.mcp_server.server import mcp_server, MCP_EXECUTION_LOG
from backend.mcp_server.tools.notifications import RECENT_NOTIFICATIONS, send_customer_sms_confirmation
from backend.mcp_server.tools.drivers import reassign_driver

class UpdateRideStatusRequest(BaseModel):
    status: str

class DriverResponseRequest(BaseModel):
    action: str  # "accept" or "decline"

router = APIRouter(prefix="/api", tags=["Admin & Operations API"])

@router.get("/stats")
def get_dashboard_stats(db: Session = Depends(get_db)):
    """Summary metrics for the admin dispatch dashboard."""
    total_drivers = db.query(Driver).count()
    available_drivers = db.query(Driver).filter(Driver.availability_status == "available").count()
    on_trip_drivers = db.query(Driver).filter(Driver.availability_status == "on_trip").count()
    offline_drivers = db.query(Driver).filter(Driver.availability_status == "offline").count()

    total_rides = db.query(Ride).count()
    active_statuses = ["pending", "confirmed", "in_progress", "booked", "driver_assigned", "driver_accepted", "driver_arriving", "ride_started"]
    active_rides = db.query(Ride).filter(Ride.status.in_(active_statuses)).count()
    completed_rides = db.query(Ride).filter(Ride.status.in_(["completed", "ride_completed"])).count()
    cancelled_rides = db.query(Ride).filter(Ride.status == "cancelled").count()

    # Breakdown of individual stages
    booked_count = db.query(Ride).filter(Ride.status.in_(["booked", "pending"])).count()
    assigned_count = db.query(Ride).filter(Ride.status.in_(["driver_assigned", "confirmed"])).count()
    accepted_count = db.query(Ride).filter(Ride.status == "driver_accepted").count()
    arriving_count = db.query(Ride).filter(Ride.status == "driver_arriving").count()
    started_count = db.query(Ride).filter(Ride.status.in_(["ride_started", "in_progress"])).count()

    return {
        "twilio_phone_number": settings.TWILIO_PHONE_NUMBER,
        "company_name": settings.COMPANY_NAME,
        "drivers": {
            "total": total_drivers,
            "available": available_drivers,
            "on_trip": on_trip_drivers,
            "offline": offline_drivers,
        },
        "rides": {
            "total": total_rides,
            "active": active_rides,
            "completed": completed_rides,
            "cancelled": cancelled_rides,
            "lifecycle": {
                "booked": booked_count,
                "driver_assigned": assigned_count,
                "driver_accepted": accepted_count,
                "driver_arriving": arriving_count,
                "ride_started": started_count,
                "ride_completed": completed_rides,
                "cancelled": cancelled_rides,
            }
        },
    }

@router.get("/drivers")
def list_drivers(
    vehicle_type: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    """Lists all drivers with optional filtering by vehicle type or availability status."""
    query = db.query(Driver)
    if vehicle_type:
        query = query.filter(Driver.vehicle_type == vehicle_type.lower())
    if status:
        query = query.filter(Driver.availability_status == status.lower())

    drivers = query.order_by(Driver.id.asc()).all()
    return [d.to_dict() for d in drivers]


@router.get("/rides")
def list_rides(
    status: Optional[str] = Query(None),
    limit: int = 50,
    db: Session = Depends(get_db),
):
    """Lists all rides with joined employee and driver details."""
    query = db.query(Ride)
    if status:
        query = query.filter(Ride.status == status.lower())

    rides = query.order_by(Ride.id.desc()).limit(limit).all()
    return [r.to_dict() for r in rides]


@router.post("/rides/{ride_id}/status")
def update_ride_status(
    ride_id: int,
    payload: UpdateRideStatusRequest,
    db: Session = Depends(get_db),
):
    """
    Updates the lifecycle status of a ride:
    'driver_accepted', 'driver_arriving', 'ride_started', 'ride_completed', 'cancelled'
    """
    ride = db.query(Ride).filter(Ride.id == ride_id).first()
    if not ride:
        raise HTTPException(status_code=404, detail=f"Ride #{ride_id} not found")

    new_status = payload.status.strip().lower()
    valid_statuses = [
        "booked", "driver_assigned", "driver_accepted",
        "driver_arriving", "ride_started", "ride_completed",
        "completed", "cancelled"
    ]
    if new_status not in valid_statuses:
        raise HTTPException(status_code=400, detail=f"Invalid status '{new_status}'. Allowed: {valid_statuses}")

    ride.status = new_status

    # Driver availability management
    if ride.driver_id:
        driver = db.query(Driver).filter(Driver.id == ride.driver_id).first()
        if driver:
            if new_status in ("completed", "ride_completed", "cancelled"):
                driver.availability_status = "available"
            elif new_status in ("driver_assigned", "driver_accepted", "driver_arriving", "ride_started"):
                driver.availability_status = "on_trip"

    db.commit()
    db.refresh(ride)
    return {
        "success": True,
        "message": f"Ride #{ride_id} status updated to '{new_status}'.",
        "ride": ride.to_dict(),
    }


@router.post("/rides/{ride_id}/driver-response")
def handle_driver_response(
    ride_id: int,
    payload: DriverResponseRequest,
    db: Session = Depends(get_db),
):
    """
    Simulates driver accepting or declining the assigned ride.
    If declined, automatically triggers the reassign_driver tool to match another driver.
    """
    ride = db.query(Ride).filter(Ride.id == ride_id).first()
    if not ride:
        raise HTTPException(status_code=404, detail=f"Ride #{ride_id} not found")

    action = payload.action.strip().lower()
    if action == "accept":
        ride.status = "driver_accepted"
        db.commit()
        db.refresh(ride)
        return {
            "success": True,
            "action": "accepted",
            "message": f"Driver {ride.driver.name if ride.driver else 'Assigned Driver'} accepted Ride #{ride.id}!",
            "ride": ride.to_dict(),
        }
    elif action == "decline":
        declining_driver_id = ride.driver_id
        declining_driver_name = ride.driver.name if ride.driver else f"Driver #{declining_driver_id}"
        reassignment = reassign_driver(
            ride_id=ride.id,
            rejected_driver_id=declining_driver_id,
            db=db,
        )
        db.refresh(ride)
        return {
            "success": True,
            "action": "declined",
            "previous_driver": declining_driver_name,
            "reassignment": reassignment,
            "ride": ride.to_dict(),
        }
    else:
        raise HTTPException(status_code=400, detail="Action must be 'accept' or 'decline'")


@router.post("/rides/{ride_id}/resend-sms")
def resend_ride_sms(
    ride_id: int,
    db: Session = Depends(get_db),
):
    """
    Resends confirmation SMS with Booking ID, driver details, and vehicle info to customer's phone.
    """
    ride = db.query(Ride).filter(Ride.id == ride_id).first()
    if not ride:
        raise HTTPException(status_code=404, detail=f"Ride #{ride_id} not found")

    customer_phone = ride.employee.phone_number if ride.employee else None
    if not customer_phone:
        raise HTTPException(status_code=400, detail="No customer phone number associated with this ride.")

    driver = ride.driver
    sms_res = send_customer_sms_confirmation(
        to_phone=customer_phone,
        ride_id=ride.id,
        pickup=ride.pickup_address or "Acme Tech Park",
        destination=ride.destination_address or "Destination",
        driver_name=driver.name if driver else "Assigned Driver",
        driver_phone=driver.phone_number if driver else "Contact Dispatch",
        vehicle_type=ride.vehicle_type or "car",
        vehicle_number=driver.vehicle_number if driver else "KA-TBD",
        fare_estimate=ride.fare_estimate,
        scheduled_time=ride.scheduled_time or "Immediate",
        passenger_count=ride.passenger_count or 1,
    )

    return {
        "success": True,
        "message": f"Confirmation SMS successfully dispatched to {customer_phone}.",
        "customer_phone": customer_phone,
        "sms_result": sms_res,
    }


@router.post("/rides/{ride_id}/complete")
def complete_ride(ride_id: int, db: Session = Depends(get_db)):
    """
    Manually marks a ride as 'completed' and frees the driver back to 'available'.
    Used for dispatch operations and testing.
    """
    ride = db.query(Ride).filter(Ride.id == ride_id).first()
    if not ride:
        raise HTTPException(status_code=404, detail="Ride not found")

    ride.status = "completed"
    if ride.driver_id:
        driver = db.query(Driver).filter(Driver.id == ride.driver_id).first()
        if driver:
            driver.availability_status = "available"

    db.commit()
    db.refresh(ride)
    return {
        "success": True,
        "message": f"Ride #{ride_id} completed. Driver freed.",
        "ride": ride.to_dict(),
    }


@router.post("/rides/{ride_id}/cancel")
def cancel_ride(ride_id: int, db: Session = Depends(get_db)):
    """Cancels a ride and frees any assigned driver."""
    ride = db.query(Ride).filter(Ride.id == ride_id).first()
    if not ride:
        raise HTTPException(status_code=404, detail="Ride not found")

    ride.status = "cancelled"
    if ride.driver_id:
        driver = db.query(Driver).filter(Driver.id == ride.driver_id).first()
        if driver and driver.availability_status == "on_trip":
            driver.availability_status = "available"

    db.commit()
    return {"success": True, "message": f"Ride #{ride_id} cancelled.", "ride": ride.to_dict()}


@router.get("/employees")
def list_employees(db: Session = Depends(get_db)):
    """Lists corporate employees for demo/identity verification."""
    employees = db.query(Employee).all()
    return [e.to_dict() for e in employees]


@router.get("/mcp/tools")
def get_mcp_tools():
    """Lists available MCP tools and recent execution metrics."""
    return {
        "tools": mcp_server.get_tool_definitions(),
        "recent_executions": list(reversed(MCP_EXECUTION_LOG[-25:])),
    }


@router.get("/notifications")
def get_recent_notifications():
    """Returns recently broadcast notifications for live dashboard display."""
    return list(reversed(RECENT_NOTIFICATIONS[-25:]))


@router.post("/reset")
def reset_demo_data():
    """Resets the database with fresh seed data for clean demo runs."""
    seed_database()
    return {"success": True, "message": "Database reset to initial seed state."}


@router.get("/reverse-geocode")
def api_reverse_geocode(lat: float = Query(...), lng: float = Query(...)):
    """
    Reverse geocodes GPS coordinates into a human-readable street address and nearest landmark.
    Used by browser geolocation buttons and mobile apps.
    """
    from backend.mcp_server.tools.location import reverse_geocode
    return reverse_geocode(lat, lng)

