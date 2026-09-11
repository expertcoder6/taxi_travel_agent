import pytest
from backend.db.database import SessionLocal, init_db
from backend.db.seed import seed_database
from backend.db.models import Driver, Employee, Ride
from backend.mcp_server.server import mcp_server

@pytest.fixture(scope="module", autouse=True)
def setup_db():
    seed_database()

def test_verify_location_valid():
    res = mcp_server.execute_tool("verify_location", {"address": "Acme Tech Park"})
    assert res["valid"] is True
    assert res["lat"] is not None
    assert res["lng"] is not None
    assert "Acme" in res["formatted_address"]

def test_verify_location_invalid():
    res = mcp_server.execute_tool("verify_location", {"address": "planet mars"})
    assert res["valid"] is False
    assert res["error_message"] is not None

def test_calculate_fare():
    # Between Acme (12.9352, 77.6944) and Indiranagar (12.9784, 77.6408)
    res = mcp_server.execute_tool(
        "calculate_fare",
        {
            "pickup_lat": 12.9352,
            "pickup_lng": 77.6944,
            "destination_lat": 12.9784,
            "destination_lng": 77.6408,
            "vehicle_type": "car",
        },
    )
    assert res["distance_km"] > 0
    assert res["fare"] > res["base_fare"]
    assert res["currency"] == "INR"

def test_check_driver_availability():
    res = mcp_server.execute_tool(
        "check_driver_availability",
        {
            "vehicle_type": "car",
            "pickup_lat": 12.9352,
            "pickup_lng": 77.6944,
            "exclude_driver_ids": [],
        },
    )
    assert res["found"] is True
    assert res["driver_id"] is not None
    assert res["name"] is not None
    assert res["vehicle_type"] == "car"

def test_assign_driver():
    db = SessionLocal()
    try:
        # Find an available driver
        driver = db.query(Driver).filter_by(vehicle_type="car", availability_status="available").first()
        assert driver is not None

        # Create a test pending ride
        ride = Ride(
            pickup_address="Acme Tech Park",
            pickup_lat=12.9352,
            pickup_lng=77.6944,
            destination_address="Koramangala",
            destination_lat=12.9352,
            destination_lng=77.6245,
            vehicle_type="car",
            fare_estimate=250.0,
            status="pending",
            channel="message",
        )
        db.add(ride)
        db.commit()
        db.refresh(ride)

        # Call assign_driver
        res = mcp_server.execute_tool("assign_driver", {"ride_id": ride.id, "driver_id": driver.id})
        assert res["success"] is True
        assert res["status"] == "confirmed"

        # Check DB state
        db.refresh(driver)
        db.refresh(ride)
        assert driver.availability_status == "on_trip"
        assert ride.status == "confirmed"
        assert ride.driver_id == driver.id
    finally:
        db.close()

def test_reassign_driver():
    db = SessionLocal()
    try:
        # Create confirmed ride
        driver1 = db.query(Driver).filter_by(vehicle_type="bike", availability_status="available").first()
        ride = Ride(
            pickup_address="Bellandur",
            pickup_lat=12.9260,
            pickup_lng=77.6762,
            destination_address="HSR Layout",
            destination_lat=12.9121,
            destination_lng=77.6446,
            vehicle_type="bike",
            fare_estimate=90.0,
            status="confirmed",
            driver_id=driver1.id,
            channel="call",
        )
        driver1.availability_status = "on_trip"
        db.add(ride)
        db.commit()
        db.refresh(ride)

        # Reassign excluding driver1
        res = mcp_server.execute_tool(
            "reassign_driver",
            {"ride_id": ride.id, "rejected_driver_id": driver1.id},
        )
        assert res["success"] is True
        assert res["new_driver"]["driver_id"] != driver1.id
    finally:
        db.close()

def test_notify_user_and_driver():
    db = SessionLocal()
    try:
        emp = db.query(Employee).first()
        drv = db.query(Driver).first()
        ride = db.query(Ride).first()

        res = mcp_server.execute_tool(
            "notify_user_and_driver",
            {"employee_id": emp.id, "driver_id": drv.id, "ride_id": ride.id},
        )
        assert res["employee_notified"] is True
        assert res["driver_notified"] is True
        assert "confirmed" in res["employee_message"].lower()
    finally:
        db.close()
