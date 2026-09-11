import time
import httpx
import sys

# Configure UTF-8 for Windows console
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

BASE_URL = "http://localhost:8000"

def test_live_system():
    with httpx.Client(base_url=BASE_URL, timeout=30.0) as client:
        print("=== 1. Checking Stats & Drivers ===")
        stats_resp = client.get("/api/stats")
        print("Stats HTTP:", stats_resp.status_code)
        assert stats_resp.status_code == 200
        stats = stats_resp.json()
        print("Initial Lifecycle breakdown:", stats["rides"]["lifecycle"])

        drivers_resp = client.get("/api/drivers")
        assert drivers_resp.status_code == 200
        drivers = drivers_resp.json()
        print(f"Total drivers available: {len([d for d in drivers if d['availability_status'] == 'available'])} / {len(drivers)}")

        print("\n=== 2. Multi-turn Booking Simulation ===")
        session_id = f"test_session_{int(time.time())}"
        test_phone = "+919644492671"

        # Turn 1: Provide all details
        payload_1 = {
            "session_id": session_id,
            "phone_number": test_phone,
            "message": "I need a ride from Indiranagar to Whitefield for 2 passengers tomorrow at 10 AM by car"
        }
        r1 = client.post("/sms/simulate", json=payload_1)
        assert r1.status_code == 200, r1.text
        data1 = r1.json()
        print("Assistant Reply Turn 1:\n", data1["reply"])
        print("Extracted Slots Turn 1:", data1["slots"])
        assert data1["slots"]["pickup"] is not None
        assert data1["slots"]["destination"] is not None
        assert data1["slots"]["passenger_count"] == 2
        assert "10" in str(data1["slots"]["scheduled_time"]) or "tomorrow" in str(data1["slots"]["scheduled_time"]).lower()

        # Turn 2: Confirm it is for self and review summary
        payload_2 = {
            "session_id": session_id,
            "phone_number": test_phone,
            "message": "It is for myself, please go ahead and verify"
        }
        r2 = client.post("/sms/simulate", json=payload_2)
        assert r2.status_code == 200, r2.text
        data2 = r2.json()
        print("\nAssistant Reply Turn 2:\n", data2["reply"])

        # Turn 3: Final confirmation to trigger book_ride
        payload_3 = {
            "session_id": session_id,
            "phone_number": test_phone,
            "message": "Yes, everything is correct, please book the ride now"
        }
        r3 = client.post("/sms/simulate", json=payload_3)
        assert r3.status_code == 200, r3.text
        data3 = r3.json()
        print("\nAssistant Reply Turn 3:\n", data3["reply"])
        print("Stage:", data3["stage"])
        ride_id = data3.get("ride_id")
        assert ride_id is not None
        print(f"Ride successfully created with ID: {ride_id}")

        print("\n=== 3. Verify Ride in Database ===")
        rides_resp = client.get("/api/rides")
        assert rides_resp.status_code == 200
        matching = [r for r in rides_resp.json() if r["id"] == ride_id]
        assert len(matching) > 0
        ride = matching[0]
        print(f"Ride status: {ride['status']}")
        print(f"Passenger count: {ride['passenger_count']}")
        print(f"Scheduled time: {ride['scheduled_time']}")
        print(f"Assigned Driver: {ride.get('driver_name')} (Phone: {ride.get('driver_phone')})")
        initial_driver_id = ride["driver_id"]
        assert initial_driver_id is not None

        print("\n=== 4. Test Driver Decline & Automatic Reassignment ===")
        decline_resp = client.post(
            f"/api/rides/{ride_id}/driver-response",
            json={"action": "decline", "reason": "Flat tire on vehicle"}
        )
        assert decline_resp.status_code == 200, decline_resp.text
        decline_data = decline_resp.json()
        new_driver_id = decline_data["ride"]["driver_id"]
        new_driver_name = decline_data["ride"]["driver_name"]
        print(f"Decline successful! Reassigned from driver {initial_driver_id} -> {new_driver_id} ({new_driver_name})")
        assert new_driver_id != initial_driver_id

        print("\n=== 5. Test Driver Accept ===")
        accept_resp = client.post(
            f"/api/rides/{ride_id}/driver-response",
            json={"action": "accept"}
        )
        assert accept_resp.status_code == 200
        accept_data = accept_resp.json()
        print(f"Driver accepted! New status: {accept_data['ride']['status']}")
        assert accept_data["ride"]["status"] == "driver_accepted"

        print("\n=== 6. Test Full Lifecycle Progression ===")
        # driver_arriving
        arriving_resp = client.post(f"/api/rides/{ride_id}/status", json={"status": "driver_arriving"})
        assert arriving_resp.status_code == 200
        print(f"Status update: {arriving_resp.json()['ride']['status']}")

        # ride_started
        started_resp = client.post(f"/api/rides/{ride_id}/status", json={"status": "ride_started"})
        assert started_resp.status_code == 200
        print(f"Status update: {started_resp.json()['ride']['status']}")

        # ride_completed
        completed_resp = client.post(f"/api/rides/{ride_id}/status", json={"status": "ride_completed"})
        assert completed_resp.status_code == 200
        print(f"Status update: {completed_resp.json()['ride']['status']}")
        assert completed_resp.json()["ride"]["status"] == "ride_completed"

        print("\n=== 7. Test Customer SMS Re-dispatch ===")
        sms_resp = client.post(f"/api/rides/{ride_id}/resend-sms")
        assert sms_resp.status_code == 200
        sms_json = sms_resp.json()
        print(f"SMS Re-dispatch response: {sms_json.get('message', sms_json)}")

        print("\n=== 8. Verify Updated Stats ===")
        final_stats = client.get("/api/stats").json()
        print("Updated Lifecycle breakdown:", final_stats["rides"]["lifecycle"])
        assert final_stats["rides"]["lifecycle"]["ride_completed"] >= 1

        print("\n>>> ALL TESTS PASSED! FULL PRODUCTION FLOW VERIFIED! <<<")

if __name__ == "__main__":
    test_live_system()
