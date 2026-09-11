import pytest
from backend.db.seed import seed_database
from backend.db.database import SessionLocal
from backend.db.models import Driver, Employee, Ride, ConversationState
from backend.agent.conversation_handler import conversation_handler

from backend.config import settings

@pytest.fixture(autouse=True)
def reset_db(monkeypatch):
    monkeypatch.setattr(settings, "OPENAI_API_KEY", "")
    seed_database()

def test_full_text_conversation_flow():
    session_id = "test_session_text_001"
    phone = "+14155552671"

    # Turn 1: Initial greeting
    res1 = conversation_handler.process_turn(session_id, "message", phone, "Hi, I need to book a ride")
    assert res1["stage"] == "gathering"
    assert "pickup" in res1["reply"].lower()

    # Turn 2: Provide pickup
    res2 = conversation_handler.process_turn(session_id, "message", phone, "From Acme Tech Park")
    assert res2["stage"] == "gathering"
    assert res2["slots"]["pickup"] is not None
    assert "destination" in res2["reply"].lower()

    # Turn 3: Provide destination
    res3 = conversation_handler.process_turn(session_id, "message", phone, "To Indiranagar")
    assert res3["stage"] == "gathering"
    assert res3["slots"]["destination"] is not None
    assert "vehicle" in res3["reply"].lower()

    # Turn 4: Select vehicle type -> Triggers Verification & Tool Calling
    res4 = conversation_handler.process_turn(session_id, "message", phone, "car")
    assert res4["stage"] == "confirmed"
    assert "confirmed" in res4["reply"].lower()
    assert res4["slots"]["vehicle_type"] == "car"
    assert len(res4["mcp_tools_called"]) >= 4

    # Verify DB changes
    db = SessionLocal()
    try:
        ride = db.query(Ride).filter(Ride.id == res4["ride_id"]).first()
        assert ride is not None
        assert ride.status == "confirmed"
        assert ride.driver_id is not None
        assert ride.fare_estimate > 0

        driver = db.query(Driver).filter(Driver.id == ride.driver_id).first()
        assert driver.availability_status == "on_trip"

        state = db.query(ConversationState).filter_by(session_id=session_id).first()
        assert state.stage == "confirmed"
    finally:
        db.close()

def test_voice_conversation_flow():
    session_id = "test_session_voice_002"
    phone = "+919876543210"

    # Turn: All-in-one utterance on voice
    res = conversation_handler.process_turn(
        session_id, "call", phone, "I need a car from Acme Tech Park to Koramangala"
    )
    assert res["stage"] == "confirmed"
    assert "Your ride is confirmed" in res["reply"]
    assert "arriving in" in res["reply"]

def test_invalid_location_handling():
    session_id = "test_session_invalid_003"
    phone = "+14155553892"

    res = conversation_handler.process_turn(
        session_id, "message", phone, "I need a bike from Nowhere on Mars to Indiranagar"
    )
    assert res["stage"] == "gathering"
    assert "couldn't verify" in res["reply"].lower() or "valid" in res["reply"].lower()

def test_reach_destination_phrasing():
    session_id = "test_session_reach_004"
    phone = "+14155552671"

    # Turn 1: specify pickup
    res1 = conversation_handler.process_turn(session_id, "message", phone, "Pickup at Acme Tech Park")
    assert res1["slots"]["pickup"] == "Acme Tech Park"
    assert "destination" in res1["reply"].lower()

    # Turn 2: specify destination using "where i have to reach is Koramangala"
    res2 = conversation_handler.process_turn(session_id, "message", phone, "where i have to reach is Koramangala")
    assert res2["slots"]["destination"] == "Koramangala"
    assert res2["slots"]["pickup"] == "Acme Tech Park"  # Must NOT overwrite pickup!
    assert "vehicle" in res2["reply"].lower()

    # Turn 3: select car
    res3 = conversation_handler.process_turn(session_id, "message", phone, "car")
    assert res3["stage"] == "confirmed"
    assert res3["slots"]["vehicle_type"] == "car"

@pytest.mark.anyio
async def test_streaming_response():
    session_id = "test_session_stream_005"
    phone = "+14155552671"

    events = []
    async for event in conversation_handler.process_turn_stream(
        session_id, "message", phone, "I need an auto from Acme Tech Park to Whitefield"
    ):
        events.append(event)

    types = [e["type"] for e in events]
    assert "slot_update" in types
    assert "tool_start" in types
    assert "tool_end" in types
    assert "token" in types
    assert "done" in types

    done_event = next(e for e in events if e["type"] == "done")
    assert done_event["stage"] == "confirmed"
    assert done_event["slots"]["vehicle_type"] == "auto"
