import pytest
from backend.db.seed import seed_database
from backend.db.database import SessionLocal
from backend.db.models import Driver, Employee, Ride, ConversationState
from backend.agent.conversation_handler import conversation_handler
from backend.mcp_server.tools.drivers import check_driver_availability
from backend.config import settings

@pytest.fixture(autouse=True)
def reset_db(monkeypatch):
    monkeypatch.setattr(settings, "OPENAI_API_KEY", "")
    seed_database()

def test_check_driver_availability_by_name():
    # Rajesh Kumar is an available car driver in seed
    res = check_driver_availability(
        vehicle_type="car",
        pickup_lat=12.9716,
        pickup_lng=77.5946,
        driver_name="Rajesh Kumar",
    )
    assert res["found"] is True
    assert res["driver_name"] == "Rajesh Kumar"
    assert res["driver_id"] == 1

def test_check_driver_availability_by_id():
    # ID 2 is Amit Sharma (Car) in seed
    res = check_driver_availability(
        vehicle_type="car",
        pickup_lat=12.9716,
        pickup_lng=77.5946,
        driver_id=2,
    )
    assert res["found"] is True
    assert res["driver_id"] == 2
    assert "Amit" in res["driver_name"]

def test_check_driver_availability_busy_or_missing():
    db = SessionLocal()
    try:
        # Mark driver 1 as on_trip
        d1 = db.query(Driver).filter(Driver.id == 1).first()
        d1.availability_status = "on_trip"
        db.commit()

        res_busy = check_driver_availability(
            vehicle_type="car",
            pickup_lat=12.9716,
            pickup_lng=77.5946,
            driver_name="Rajesh Kumar",
        )
        assert res_busy["found"] is False
        assert "on trip" in res_busy["message"].lower()

        res_missing = check_driver_availability(
            vehicle_type="car",
            pickup_lat=12.9716,
            pickup_lng=77.5946,
            driver_name="Nonexistent Driver XYZ",
        )
        assert res_missing["found"] is False
        assert "not found" in res_missing["message"].lower()
    finally:
        db.close()

def test_requested_driver_slot_extraction():
    db = SessionLocal()
    try:
        emp = db.query(Employee).first()
        state = ConversationState(session_id="test_extract_drv", channel="message", employee_phone=emp.phone_number)
        ride = Ride(employee_id=emp.id, pickup_address="Acme Tech Park", status="pending")

        # Extraction with "with driver Rajesh Kumar"
        conversation_handler.extract_slots(state, ride, "I want to book with driver Rajesh Kumar from Acme Tech Park to Koramangala")
        assert state.requested_driver == "Rajesh Kumar"
        assert ride.requested_driver == "Rajesh Kumar"
        assert ride.driver_id == 1
        assert state.destination == "Koramangala"
        assert "Acme Tech Park" in state.pickup
    finally:
        db.close()

def test_destination_not_corrupted_by_confirmation_phrase():
    db = SessionLocal()
    try:
        emp = db.query(Employee).first()
        state = ConversationState(
            session_id="test_confirm_corrupt",
            channel="message",
            employee_phone=emp.phone_number,
            pickup="Acme Tech Park",
            destination="Koramangala",
            vehicle_type="car",
            messages_json='[{"role": "assistant", "content": "Pickup: Acme Tech Park, Destination: Koramangala. Fare: ₹150. Driver: Rajesh Kumar. Would you like to confirm?"}]',
        )
        ride = Ride(
            employee_id=emp.id,
            pickup_address="Acme Tech Park",
            destination_address="Koramangala",
            vehicle_type="car",
            driver_id=1,
            status="pending",
        )

        # User confirms with natural phrases
        confirm_phrases = [
            "Yes, please confirm and book it",
            "Yes, Book It Now",
            "yes confirm",
            "Book it please",
            "confirm ride",
            "yes please",
        ]

        for phrase in confirm_phrases:
            conversation_handler.extract_slots(state, ride, phrase)
            # Destination MUST stay Koramangala, NEVER become the confirmation phrase!
            assert state.destination == "Koramangala", f"Destination was corrupted by phrase: '{phrase}'"
            assert ride.destination_address == "Koramangala"
    finally:
        db.close()

def test_full_conversation_with_specific_driver():
    session_id = "test_driver_booking_full"
    phone = "+14155552671"

    # User explicitly books with driver Amit Sharma
    res = conversation_handler.process_turn(
        session_id=session_id,
        channel="message",
        employee_phone=phone,
        user_text="I want to book with driver Amit Sharma from Acme Tech Park to Koramangala",
    )

    assert res["stage"] == "confirmed"
    assert res["slots"]["requested_driver"] == "Amit Sharma"
    assert "confirmed" in res["reply"].lower()
    assert "amit" in res["reply"].lower()

    db = SessionLocal()
    try:
        ride = db.query(Ride).filter(Ride.id == res["ride_id"]).first()
        assert ride is not None
        assert ride.status == "confirmed"
        # Must be assigned to Amit Sharma (ID 2 in seed)
        assert ride.driver_id == 2
        assert ride.requested_driver == "Amit Sharma"

        driver = db.query(Driver).filter(Driver.id == 2).first()
        assert driver.name == "Amit Sharma"
        assert driver.availability_status == "on_trip"
    finally:
        db.close()
