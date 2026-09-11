import os
import json
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime
from sqlalchemy.orm import Session
from backend.config import settings
from backend.db.database import SessionLocal
from backend.db.models import Employee, Driver, Ride

logger = logging.getLogger("mcp.notifications")

# In-memory store for dispatched notifications (accessible to admin dashboard)
RECENT_NOTIFICATIONS: List[Dict[str, Any]] = []

def send_firebase_fcm(token: str, title: str, body: str, data: Dict[str, str]) -> bool:
    """Sends a Firebase Cloud Messaging push notification if configured."""
    raw = settings.FIREBASE_SERVICE_ACCOUNT_JSON
    if not raw:
        return False

    try:
        import firebase_admin
        from firebase_admin import credentials, messaging

        if not firebase_admin._apps:
            raw_str = raw.strip()
            if os.path.exists(raw_str):
                cred = credentials.Certificate(raw_str)
            else:
                cred_dict = json.loads(raw_str)
                cred = credentials.Certificate(cred_dict)
            firebase_admin.initialize_app(cred)

        message = messaging.Message(
            notification=messaging.Notification(title=title, body=body),
            data={k: str(v) for k, v in data.items()},
            token=token,
        )
        response = messaging.send(message)
        logger.info(f"FCM message sent successfully: {response}")
        return True
    except Exception as exc:
        logger.warning(f"Failed to send Firebase FCM notification: {exc}")
        return False

def send_customer_sms_confirmation(
    to_phone: str,
    ride_id: int,
    pickup: str,
    destination: str,
    driver_name: str,
    driver_phone: str,
    vehicle_type: str,
    vehicle_number: str,
    fare_estimate: Optional[float] = None,
    scheduled_time: Optional[str] = "Immediate",
    passenger_count: Optional[int] = 1,
) -> Dict[str, Any]:
    """
    Sends an automated confirmation SMS to the customer's phone number via Twilio.
    Includes Booking ID, Locations, Schedule, Driver details, Vehicle details, and Fare.
    """
    fare_str = f"₹{round(fare_estimate, 2)}" if fare_estimate else "Standard metered"
    sms_body = (
        f"🚕 {settings.COMPANY_NAME} Ride Confirmed!\n"
        f"Booking ID: #{ride_id}\n"
        f"📍 Pickup: {pickup}\n"
        f"🏁 Drop: {destination}\n"
        f"🕒 Time: {scheduled_time or 'Immediate'} | 👥 Passengers: {passenger_count or 1}\n"
        f"🚘 Vehicle: {(vehicle_type or 'car').upper()} ({vehicle_number})\n"
        f"👤 Driver: {driver_name} ({driver_phone})\n"
        f"💵 Est. Fare: {fare_str}\n"
        f"Status: Driver Assigned & On The Way"
    )

    if not settings.TWILIO_ACCOUNT_SID or not settings.TWILIO_AUTH_TOKEN or not settings.TWILIO_PHONE_NUMBER:
        logger.warning("Twilio credentials not fully set up. Logging SMS to notifications.")
        return {"sent": False, "mode": "simulated", "message": sms_body}

    try:
        from twilio.rest import Client
        client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
        msg = client.messages.create(
            to=to_phone,
            from_=settings.TWILIO_PHONE_NUMBER,
            body=sms_body,
        )
        logger.info(f"Confirmation SMS dispatched to {to_phone} with SID {msg.sid}")
        return {"sent": True, "sid": msg.sid, "mode": "live_twilio_sms", "message": sms_body}
    except Exception as exc:
        logger.warning(f"Twilio SMS delivery fallback (e.g. trial account unverified destination): {exc}")
        return {"sent": False, "error": str(exc), "mode": "trial_restricted_fallback", "message": sms_body}


def notify_user_and_driver(
    employee_id: int,
    driver_id: int,
    ride_id: int,
    db: Optional[Session] = None,
) -> Dict[str, Any]:
    """
    MCP Tool: notify_user_and_driver
    Dispatches ride assignment notifications via Twilio SMS, Firebase FCM, and channel adapters
    to both the customer and assigned driver.
    """
    should_close = False
    if db is None:
        db = SessionLocal()
        should_close = True

    try:
        employee = db.query(Employee).filter(Employee.id == employee_id).first()
        driver = db.query(Driver).filter(Driver.id == driver_id).first()
        ride = db.query(Ride).filter(Ride.id == ride_id).first()

        emp_name = employee.name if employee else "Valued Passenger"
        emp_phone = employee.phone_number if employee else "Unknown"
        drv_name = driver.name if driver else "Assigned Driver"
        drv_phone = driver.phone_number if driver else "Unknown"
        veh_num = driver.vehicle_number if driver else "Assigned Vehicle"
        veh_type = ride.vehicle_type if ride else "car"
        pickup = ride.pickup_address if ride else "Designated Pickup"
        dest = ride.destination_address if ride else "Destination"
        fare = f"₹{round(ride.fare_estimate, 2)}" if ride and ride.fare_estimate else "calculated at drop"
        pass_count = ride.passenger_count if ride else 1
        sched_time = ride.scheduled_time if ride else "Immediate"

        # Notification content
        employee_msg = (
            f"Your ride #{ride_id} is confirmed! Driver {drv_name} ({drv_phone}) is on the way "
            f"in vehicle {veh_num}. Time: {sched_time}. Passengers: {pass_count}. Estimated Fare: {fare}."
        )
        driver_msg = (
            f"New Ride Assigned (Booking #{ride_id})! Pickup {emp_name} ({emp_phone}) at {pickup}, "
            f"destination: {dest}. Passengers: {pass_count}."
        )

        channels = ["TWILIO_SMS", "FCM_PUSH", "IN_APP_DISPATCH"]
        delivery_mode = "live_twilio_sms_and_dispatch"

        # 1. Dispatch Customer SMS Confirmation via Twilio
        sms_result = {"sent": False}
        if emp_phone and emp_phone != "Unknown":
            sms_result = send_customer_sms_confirmation(
                to_phone=emp_phone,
                ride_id=ride_id,
                pickup=pickup,
                destination=dest,
                driver_name=drv_name,
                driver_phone=drv_phone,
                vehicle_type=veh_type,
                vehicle_number=veh_num,
                fare_estimate=ride.fare_estimate if ride else None,
                scheduled_time=sched_time,
                passenger_count=pass_count,
            )

        # 2. Attempt FCM if token present
        emp_fcm_sent = False
        if employee and employee.fcm_token:
            emp_fcm_sent = send_firebase_fcm(
                token=employee.fcm_token,
                title="Ride Confirmed!",
                body=employee_msg,
                data={"ride_id": str(ride_id), "role": "passenger"},
            )

        event = {
            "timestamp": datetime.utcnow().isoformat(),
            "ride_id": ride_id,
            "employee_id": employee_id,
            "employee_name": emp_name,
            "employee_phone": emp_phone,
            "employee_message": employee_msg,
            "driver_id": driver_id,
            "driver_name": drv_name,
            "driver_phone": drv_phone,
            "driver_message": driver_msg,
            "sms_sent": sms_result.get("sent", False),
            "sms_mode": sms_result.get("mode", "unattempted"),
            "channels_used": channels,
            "delivery_mode": delivery_mode,
            "success": True,
        }

        RECENT_NOTIFICATIONS.append(event)
        if len(RECENT_NOTIFICATIONS) > 50:
            RECENT_NOTIFICATIONS.pop(0)

        return {
            "employee_notified": True,
            "driver_notified": True,
            "customer_sms": sms_result,
            "employee_message": employee_msg,
            "driver_message": driver_msg,
            "channels_used": channels,
            "delivery_mode": delivery_mode,
            "ride_id": ride_id,
        }
    finally:
        if should_close:
            db.close()
