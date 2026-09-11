import pytest
from fastapi.testclient import TestClient
from backend.main import app
from backend.db.seed import seed_database
from backend.db.database import SessionLocal
from backend.db.models import Driver, Ride

from backend.config import settings

client = TestClient(app)

@pytest.fixture(autouse=True)
def init_data(monkeypatch):
    monkeypatch.setattr(settings, "OPENAI_API_KEY", "")
    seed_database()

def test_health_check():
    res = client.get("/")
    assert res.status_code == 200
    assert res.json()["status"] == "healthy"

def test_twilio_sms_incoming_twiml():
    res = client.post(
        "/sms/incoming",
        data={"From": "+14155552671", "Body": "Need a car from Acme Tech Park to Whitefield"},
    )
    assert res.status_code == 200
    assert "application/xml" in res.headers["content-type"]
    assert "<Response>" in res.text
    assert "<Message>" in res.text

def test_simulate_sms_json():
    res = client.post(
        "/sms/simulate",
        json={
            "session_id": "api_test_sms_1",
            "phone_number": "+14155552671",
            "message": "I need a bike from Acme Tech Park to Koramangala",
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert data["stage"] == "confirmed"
    assert "confirmed" in data["reply"].lower()
    assert len(data["mcp_tools_called"]) >= 4

def test_twilio_voice_inbound():
    res = client.post("/voice/inbound", data={"From": "+14155552671", "CallSid": "CA123456"})
    assert res.status_code == 200
    assert "application/xml" in res.headers["content-type"]
    assert "<Gather" in res.text
    assert "Polly.Joanna-Neural" in res.text

def test_voice_simulate():
    res = client.post(
        "/voice/simulate",
        json={
            "session_id": "api_test_voice_1",
            "phone_number": "+919876543210",
            "user_text": "I want an auto from Acme Tech Park to Bellandur",
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert data["stage"] == "confirmed"
    assert "confirmed" in data["reply"].lower()

def test_api_drivers_list():
    res = client.get("/api/drivers")
    assert res.status_code == 200
    drivers = res.json()
    assert len(drivers) >= 20

def test_api_complete_ride():
    # First book a ride
    book_res = client.post(
        "/sms/simulate",
        json={
            "session_id": "comp_test_1",
            "phone_number": "+14155552671",
            "message": "Car from Acme Tech Park to MG Road",
        },
    )
    ride_id = book_res.json()["ride_id"]
    assert ride_id is not None

    # Check that driver is now on_trip
    db = SessionLocal()
    ride = db.query(Ride).filter(Ride.id == ride_id).first()
    driver = db.query(Driver).filter(Driver.id == ride.driver_id).first()
    assert driver.availability_status == "on_trip"
    db.close()

    # Complete the ride via API
    comp_res = client.post(f"/api/rides/{ride_id}/complete")
    assert comp_res.status_code == 200
    assert comp_res.json()["success"] is True

    # Check driver is freed back to available
    db = SessionLocal()
    driver = db.query(Driver).filter(Driver.id == ride.driver_id).first()
    assert driver.availability_status == "available"
    db.close()

def test_api_mcp_tools_and_notifications():
    res_mcp = client.get("/api/mcp/tools")
    assert res_mcp.status_code == 200
    assert len(res_mcp.json()["tools"]) >= 6

    res_notif = client.get("/api/notifications")
    assert res_notif.status_code == 200
    assert isinstance(res_notif.json(), list)

def test_reverse_geocode_api():
    res = client.get("/api/reverse-geocode?lat=12.9352&lng=77.6245")
    assert res.status_code == 200
    data = res.json()
    assert data["valid"] is True
    assert "Koramangala" in data["formatted_address"]

def test_ride_lifecycle_status_transitions():
    # Book a ride
    book_res = client.post(
        "/sms/simulate",
        json={
            "session_id": "lifecycle_test_1",
            "phone_number": "+919644492671",
            "message": "Car from Acme Tech Park to Koramangala for 2 passengers",
        },
    )
    ride_id = book_res.json()["ride_id"]
    assert ride_id is not None

    # 1. Driver Accept
    acc_res = client.post(f"/api/rides/{ride_id}/driver-response", json={"action": "accept"})
    assert acc_res.status_code == 200
    assert acc_res.json()["ride"]["status"] == "driver_accepted"

    # 2. Driver Arriving
    arr_res = client.post(f"/api/rides/{ride_id}/status", json={"status": "driver_arriving"})
    assert arr_res.status_code == 200
    assert arr_res.json()["ride"]["status"] == "driver_arriving"

    # 3. Ride Started
    start_res = client.post(f"/api/rides/{ride_id}/status", json={"status": "ride_started"})
    assert start_res.status_code == 200
    assert start_res.json()["ride"]["status"] == "ride_started"

    # 4. Ride Completed
    comp_res = client.post(f"/api/rides/{ride_id}/complete")
    assert comp_res.status_code == 200
    assert comp_res.json()["ride"]["status"] == "completed"

def test_driver_decline_and_reassign():
    book_res = client.post(
        "/sms/simulate",
        json={
            "session_id": "decline_test_1",
            "phone_number": "+919644492671",
            "message": "Auto from Acme Tech Park to Indiranagar",
        },
    )
    ride_id = book_res.json()["ride_id"]
    initial_driver_id = book_res.json()["mcp_tools_called"][-2]["result"]["driver_id"]

    # Driver Declines -> triggers automatic reassignment
    dec_res = client.post(f"/api/rides/{ride_id}/driver-response", json={"action": "decline"})
    assert dec_res.status_code == 200
    assert dec_res.json()["action"] == "declined"
    assert dec_res.json()["reassignment"]["success"] is True
    assert dec_res.json()["reassignment"]["new_driver"]["driver_id"] != initial_driver_id

