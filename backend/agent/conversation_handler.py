import json
import logging
import re
import asyncio
from typing import Dict, Any, List, Optional, AsyncGenerator
from sqlalchemy.orm import Session

from backend.config import settings
from backend.db.database import SessionLocal
from backend.db.models import ConversationState, Employee, Ride, Driver
from backend.agent.prompts import get_system_prompt
from backend.agent.mcp_client import mcp_client
from backend.mcp_server.server import mcp_server

logger = logging.getLogger("agent.conversation")

class ConversationHandler:
    """
    Unified Conversational Slot-Filling & Tool Orchestration Engine.
    Handles both Voice Call and Text Message channels using the same state pipeline,
    with full streaming response capabilities and robust multi-turn slot extraction.
    """

    def get_or_create_employee(self, db: Session, phone_number: str) -> Employee:
        normalized_phone = (phone_number or "+1234567890").strip()
        employee = db.query(Employee).filter(Employee.phone_number == normalized_phone).first()
        if not employee:
            employee = Employee(
                name=f"Employee ({normalized_phone[-4:]})",
                phone_number=normalized_phone,
                fcm_token=f"fcm_token_{normalized_phone.replace('+', '')}",
            )
            db.add(employee)
            db.commit()
            db.refresh(employee)
        return employee

    def get_or_create_state(
        self, db: Session, session_id: str, channel: str, employee_phone: str
    ) -> ConversationState:
        state = db.query(ConversationState).filter(ConversationState.session_id == session_id).first()
        if not state:
            state = ConversationState(
                session_id=session_id,
                channel=channel,
                employee_phone=employee_phone,
                stage="gathering",
                messages_json="[]",
            )
            db.add(state)
            db.commit()
            db.refresh(state)
        return state

    def get_or_create_ride(
        self, db: Session, state: ConversationState, employee: Employee
    ) -> Ride:
        if state.active_ride_id:
            ride = db.query(Ride).filter(Ride.id == state.active_ride_id).first()
            if ride:
                return ride

        ride = Ride(
            employee_id=employee.id,
            status="pending",
            channel=state.channel,
            vehicle_type=state.vehicle_type or "car",
            pickup_address=state.pickup,
            destination_address=state.destination,
            passenger_count=state.passenger_count or 1,
            scheduled_time=state.scheduled_time or "Immediate",
        )
        db.add(ride)
        db.commit()
        db.refresh(ride)
        state.active_ride_id = ride.id
        db.commit()
        return ride

    def extract_slots(
        self,
        state: ConversationState,
        ride: Ride,
        user_text: str,
    ) -> None:
        """
        Extracts pickup, destination, vehicle_type, and travel intent with high accuracy.
        Handles phrases like 'where i have to reach', 'reach Koramangala', 'pickup from', 'drop at', etc.
        """
        text = user_text.lower().strip()

        # Check what the previous assistant prompt was asking for
        last_assistant_msg = ""
        try:
            history = json.loads(state.messages_json or "[]")
            for m in reversed(history):
                if m.get("role") == "assistant":
                    last_assistant_msg = m.get("content", "").lower()
                    break
        except Exception:
            pass

        # Did the assistant explicitly ask for destination or pickup?
        asking_for_dest = bool(
            re.search(
                r"\b(where\s+is\s+your\s+destination|where\s+should\s+we\s+drop\s+you|where\s+to\s+drop|destination|drop\s+off)\b",
                last_assistant_msg,
            )
        )
        asking_for_pickup = (
            not asking_for_dest
            and bool(
                re.search(
                    r"\b(where\s+would\s+you\s+like\s+to\s+be\s+picked\s+up|where\s+is\s+your\s+pickup|pickup\s+location)\b",
                    last_assistant_msg,
                )
            )
        )

        # 1. Vehicle type extraction
        for v in ("bike", "auto", "car"):
            if re.search(rf"\b{v}\b", text):
                state.vehicle_type = v
                ride.vehicle_type = v

        # 2. Self vs Someone else
        if re.search(r"\b(someone\s+else|colleague|friend|for\s+others?)\b", text):
            state.booking_for_self = 0
        elif re.search(r"\b(myself|for\s+me|self)\b", text):
            state.booking_for_self = 1

        # 3. Company location references
        if re.search(r"\b(to\s+office|to\s+company|to\s+work|to\s+acme)\b", text):
            state.destination = settings.COMPANY_LOCATION_NAME
        elif re.search(r"\b(from\s+office|from\s+company|from\s+work|from\s+acme)\b", text):
            state.pickup = settings.COMPANY_LOCATION_NAME

        # 4. Explicit Destination patterns
        # Matches: "where i have to reach is X", "i have to reach X", "have to reach X", "reach at X", "reach X"
        # Matches: "drop me at X", "drop at X", "drop to X", "destination is X", "destination X"
        dest_match = re.search(
            r"\b(?:where\s+i\s+have\s+to\s+reach(?:\s+is|\s+at|\s+to)?|i\s+have\s+to\s+reach(?:\s+at|\s+to)?|have\s+to\s+reach(?:\s+at|\s+to)?|want\s+to\s+reach(?:\s+at|\s+to)?|reach\s+at|reach\s+to|reach|drop\s+off\s+at|drop\s+me\s+off\s+at|drop\s+me\s+at|drop\s+me\s+to|drop\s+at|drop\s+to|destination\s+is|destination\s*:\s*|destination)\s+([a-zA-Z0-9\s,\-\.]+?)(?:\s+(?:from|pickup|by|in|with|and\s+(?:book|i\s+want|vehicle|car|bike|auto))\s+|$)",
            text,
        )
        if dest_match:
            dest_val = dest_match.group(1).strip()
            dest_val = re.sub(r"\s+and\s+(?:book|i\s+want|vehicle|car|bike|auto).*$", "", dest_val, flags=re.IGNORECASE)
            if dest_val and dest_val not in ("car", "bike", "auto"):
                state.destination = " ".join(w.capitalize() for w in dest_val.split())

        # 5. Explicit Pickup & GPS / Current Location patterns
        pickup_match = re.search(
            r"\b(?:my\s+current\s+location(?:\s+is|\s*:)?|use\s+my\s+current\s+location(?:\s+as\s+pickup|\s*:)?|current\s+location(?:\s+is|\s*:)?|gps\s+location(?:\s+is|\s*:)?|i\s+am\s+at|i'm\s+at|here\s+at|pick\s+me\s+up\s+from|pick\s+me\s+up\s+at|pickup\s+from|pickup\s+at|pickup\s+is|pickup\s*:\s*|pickup|start\s+from)\s+([a-zA-Z0-9\s,\-\.\(\)]+?)(?:\s+(?:to|reach|drop|by|in|with|and\s+(?:book|i\s+want|vehicle|car|bike|auto))\s+|$)",
            text,
        )
        if pickup_match:
            pick_val = pickup_match.group(1).strip()
            pick_val = re.sub(r"\s+and\s+(?:book|i\s+want|vehicle|car|bike|auto).*$", "", pick_val, flags=re.IGNORECASE)
            if pick_val and pick_val not in ("car", "bike", "auto"):
                state.pickup = " ".join(w.capitalize() for w in pick_val.split())

        # 6. Preposition matching: "from X" and "to Y"
        from_match = re.search(r"\bfrom\s+([a-zA-Z0-9\s,\-\.]+?)(?:\s+(?:to|reach|drop|by|in|with)\s+|$)", text)
        if from_match and not state.pickup:
            state.pickup = " ".join(w.capitalize() for w in from_match.group(1).strip().split())

        is_generic_intent = bool(re.search(r"\b(need|want|like|trying)\s+to\s+(book|take|get|go|travel|reserve|catch|order|request)\b", text))
        if not is_generic_intent and not state.destination:
            to_match = re.search(
                r"\bto\s+(?!(?:book|take|get|go|travel|reserve|catch|order|request)\b)([a-zA-Z0-9\s,\-\.]+?)(?:\s+(?:from|by|in|with)\s+|$)",
                text,
            )
            if to_match:
                state.destination = " ".join(w.capitalize() for w in to_match.group(1).strip().split())

        # 7. Contextual single-slot response
        clean_ans = user_text.strip()
        clean_stripped = re.sub(r"^(?:hi|hello|hey|good\s+(?:morning|afternoon|evening))[,\s!]*", "", clean_ans.lower()).strip()
        is_greeting_or_intent = (
            not clean_stripped
            or bool(re.search(r"^(?:i\s+)?(?:need|want|would\s+like)\s+(?:to\s+)?(?:book|get|take|order)?\s*(?:a\s+)?ride[s\s\.\?!]*$", clean_stripped))
            or clean_stripped in ("book a ride", "need a ride", "car", "bike", "auto")
        )
        # 8. Passenger count extraction
        pass_match = re.search(r"\b(\d+)\s*(?:passengers?|people|persons?|riders?|seats?)\b", text)
        if pass_match:
            try:
                state.passenger_count = int(pass_match.group(1))
            except Exception:
                pass
        elif re.search(r"\b(?:for\s+)?(\d+)\s+of\s+us\b", text):
            m = re.search(r"\b(?:for\s+)?(\d+)\s+of\s+us\b", text)
            if m:
                state.passenger_count = int(m.group(1))
        elif re.search(r"\b(two|three|four)\s+(?:passengers?|people|persons?|riders?)\b", text):
            word_map = {"two": 2, "three": 3, "four": 4}
            w_match = re.search(r"\b(two|three|four)\s+(?:passengers?|people|persons?|riders?)\b", text)
            if w_match:
                state.passenger_count = word_map.get(w_match.group(1), 1)
        elif re.search(r"\b(just\s+me|solo|only\s+me|single|1\s+person|myself\s+alone)\b", text):
            state.passenger_count = 1

        # 9. Scheduled time extraction
        time_match = re.search(r"\b(?:at|by|for|around)\s+(\d{1,2}(?::\d{2})?\s*(?:am|pm))\b", text)
        if time_match:
            state.scheduled_time = time_match.group(1).upper()
        elif re.search(r"\b(tomorrow(?:\s+morning|\s+evening|\s+afternoon)?)\b", text):
            tm = re.search(r"\b(tomorrow(?:\s+morning|\s+evening|\s+afternoon)?)\b", text)
            if tm:
                state.scheduled_time = tm.group(1).title()
        elif re.search(r"\b(right\s+now|immediately|asap|now|urgent)\b", text):
            state.scheduled_time = "Immediate"

        if not is_greeting_or_intent and not dest_match and not pickup_match and not from_match:
            formatted_ans = " ".join(w.capitalize() for w in clean_ans.split())
            if asking_for_dest or (state.pickup and not state.destination):
                state.destination = formatted_ans
            elif asking_for_pickup or not state.pickup:
                state.pickup = formatted_ans

        # Synchronize ride with extracted state
        if state.pickup:
            ride.pickup_address = state.pickup
        if state.destination:
            ride.destination_address = state.destination
        if state.vehicle_type:
            ride.vehicle_type = state.vehicle_type
        if state.passenger_count:
            ride.passenger_count = state.passenger_count
        if state.scheduled_time:
            ride.scheduled_time = state.scheduled_time

    def process_turn(
        self,
        session_id: str,
        channel: str,
        employee_phone: str,
        user_text: str,
    ) -> Dict[str, Any]:
        """
        Processes a single conversational turn from voice (post-STT) or message.
        """
        db = SessionLocal()
        tools_called_this_turn: List[Dict[str, Any]] = []

        try:
            employee = self.get_or_create_employee(db, employee_phone)
            state = self.get_or_create_state(db, session_id, channel, employee.phone_number)
            ride = self.get_or_create_ride(db, state, employee)

            messages: List[Dict[str, Any]] = []
            try:
                messages = json.loads(state.messages_json or "[]")
            except Exception:
                messages = []

            messages.append({"role": "user", "content": user_text})

            # Pre-extract slots so state and LLM system prompt are always synchronized
            self.extract_slots(state, ride, user_text)
            db.commit()

            use_openai = bool(settings.OPENAI_API_KEY and settings.OPENAI_API_KEY.strip())
            reply_text = ""

            if use_openai:
                reply_text = self._process_with_openai(
                    db=db,
                    state=state,
                    ride=ride,
                    employee=employee,
                    messages=messages,
                    tools_called_this_turn=tools_called_this_turn,
                )
            else:
                reply_text = self._process_with_rule_engine(
                    db=db,
                    state=state,
                    ride=ride,
                    employee=employee,
                    user_text=user_text,
                    tools_called_this_turn=tools_called_this_turn,
                )

            messages.append({"role": "assistant", "content": reply_text})
            state.messages_json = json.dumps(messages)
            db.commit()
            db.refresh(state)

            return {
                "session_id": session_id,
                "channel": channel,
                "reply": reply_text,
                "stage": state.stage,
                "slots": {
                    "pickup": state.pickup,
                    "destination": state.destination,
                    "vehicle_type": state.vehicle_type,
                    "passenger_count": state.passenger_count or 1,
                    "scheduled_time": state.scheduled_time or "Immediate",
                    "booking_for_self": bool(state.booking_for_self),
                },
                "ride_id": state.active_ride_id,
                "employee": {
                    "id": employee.id,
                    "name": employee.name,
                    "phone": employee.phone_number,
                },
                "mcp_tools_called": tools_called_this_turn,
            }

        finally:
            db.close()

    async def process_turn_stream(
        self,
        session_id: str,
        channel: str,
        employee_phone: str,
        user_text: str,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Asynchronously streams conversational turn tokens and MCP tool lifecycle events
        for live real-time UI typing and animated slot updates.
        """
        db = SessionLocal()
        tools_called_this_turn: List[Dict[str, Any]] = []

        try:
            employee = self.get_or_create_employee(db, employee_phone)
            state = self.get_or_create_state(db, session_id, channel, employee.phone_number)
            ride = self.get_or_create_ride(db, state, employee)

            messages: List[Dict[str, Any]] = []
            try:
                messages = json.loads(state.messages_json or "[]")
            except Exception:
                messages = []

            messages.append({"role": "user", "content": user_text})

            # Emit initial slot status
            yield {
                "type": "slot_update",
                "stage": state.stage,
                "slots": {
                    "pickup": state.pickup,
                    "destination": state.destination,
                    "vehicle_type": state.vehicle_type,
                    "passenger_count": state.passenger_count or 1,
                    "scheduled_time": state.scheduled_time or "Immediate",
                    "booking_for_self": bool(state.booking_for_self),
                },
            }

            # Pre-extract slots so state and LLM system prompt are always synchronized
            self.extract_slots(state, ride, user_text)
            db.commit()

            yield {
                "type": "slot_update",
                "stage": state.stage,
                "slots": {
                    "pickup": state.pickup,
                    "destination": state.destination,
                    "vehicle_type": state.vehicle_type,
                    "passenger_count": state.passenger_count or 1,
                    "scheduled_time": state.scheduled_time or "Immediate",
                    "booking_for_self": bool(state.booking_for_self),
                },
            }

            use_openai = bool(settings.OPENAI_API_KEY and settings.OPENAI_API_KEY.strip())
            reply_text = ""

            if use_openai:
                # Execute OpenAI with tool loop
                reply_text = self._process_with_openai(
                    db=db,
                    state=state,
                    ride=ride,
                    employee=employee,
                    messages=messages,
                    tools_called_this_turn=tools_called_this_turn,
                )
                # Stream out the reply tokens
                words = reply_text.split(" ")
                for i, word in enumerate(words):
                    chunk = word + (" " if i < len(words) - 1 else "")
                    yield {"type": "token", "chunk": chunk}
                    await asyncio.sleep(0.015)
            else:
                # Rule engine with real-time event streaming
                pass

                yield {
                    "type": "slot_update",
                    "stage": state.stage,
                    "slots": {
                        "pickup": state.pickup,
                        "destination": state.destination,
                        "vehicle_type": state.vehicle_type,
                        "booking_for_self": bool(state.booking_for_self),
                    },
                }

                # Check missing slots
                missing_slots = []
                if not state.pickup:
                    missing_slots.append("pickup location")
                if not state.destination:
                    missing_slots.append("destination location")
                if not state.vehicle_type:
                    missing_slots.append("vehicle type (car, bike, or auto)")

                if missing_slots:
                    state.stage = "gathering"
                    db.commit()
                    if "pickup location" in missing_slots:
                        reply_text = (
                            f"Hello {employee.name}! Where would you like to be picked up from today?"
                            if state.channel == "call"
                            else f"Hello {employee.name}! 👋 Where is your pickup location?"
                        )
                    elif "destination location" in missing_slots:
                        reply_text = (
                            f"Got it, pickup at {state.pickup}. Where should we drop you off?"
                            if state.channel == "call"
                            else f"Pickup noted at {state.pickup}. Where is your destination?"
                        )
                    else:
                        reply_text = (
                            "Which vehicle would you prefer? We offer car, bike, or auto."
                            if state.channel == "call"
                            else "Please choose your vehicle type: Car 🚗, Bike 🏍️, or Auto 🛺."
                        )
                else:
                    # Stage: VERIFYING
                    state.stage = "verifying"
                    db.commit()
                    yield {
                        "type": "slot_update",
                        "stage": state.stage,
                        "slots": {
                            "pickup": state.pickup,
                            "destination": state.destination,
                            "vehicle_type": state.vehicle_type,
                        },
                    }

                    # Verify pickup
                    yield {"type": "tool_start", "name": "verify_location", "arguments": {"address": state.pickup, "location_type": "pickup"}}
                    v_pick = mcp_server.execute_tool("verify_location", {"address": state.pickup, "location_type": "pickup"})
                    tools_called_this_turn.append({"name": "verify_location", "arguments": {"address": state.pickup, "location_type": "pickup"}, "result": v_pick})
                    yield {"type": "tool_end", "name": "verify_location", "result": v_pick}

                    if not v_pick.get("valid"):
                        state.pickup = None
                        state.stage = "gathering"
                        db.commit()
                        reply_text = f"I couldn't verify that pickup location: {v_pick.get('error_message')}. Could you please specify a recognizable landmark or street?"
                    else:
                        # Verify destination
                        yield {"type": "tool_start", "name": "verify_location", "arguments": {"address": state.destination, "location_type": "destination"}}
                        v_dest = mcp_server.execute_tool("verify_location", {"address": state.destination, "location_type": "destination"})
                        tools_called_this_turn.append({"name": "verify_location", "arguments": {"address": state.destination, "location_type": "destination"}, "result": v_dest})
                        yield {"type": "tool_end", "name": "verify_location", "result": v_dest}

                        if not v_dest.get("valid"):
                            state.destination = None
                            state.stage = "gathering"
                            db.commit()
                            reply_text = f"I couldn't verify that destination: {v_dest.get('error_message')}. Could you please provide a valid drop-off area?"
                        else:
                            # Both valid -> Update coordinates
                            state.pickup = v_pick["formatted_address"]
                            state.destination = v_dest["formatted_address"]
                            ride.pickup_address = state.pickup
                            ride.pickup_lat = v_pick["lat"]
                            ride.pickup_lng = v_pick["lng"]
                            ride.destination_address = state.destination
                            ride.destination_lat = v_dest["lat"]
                            ride.destination_lng = v_dest["lng"]
                            ride.vehicle_type = state.vehicle_type
                            state.stage = "tool_calling"
                            db.commit()

                            yield {
                                "type": "slot_update",
                                "stage": state.stage,
                                "slots": {
                                    "pickup": state.pickup,
                                    "destination": state.destination,
                                    "vehicle_type": state.vehicle_type,
                                },
                            }

                            # Tool 1: check driver availability
                            yield {"type": "tool_start", "name": "check_driver_availability", "arguments": {"vehicle_type": state.vehicle_type, "pickup_lat": ride.pickup_lat, "pickup_lng": ride.pickup_lng}}
                            driver_check = mcp_server.execute_tool(
                                "check_driver_availability",
                                {
                                    "vehicle_type": state.vehicle_type,
                                    "pickup_lat": ride.pickup_lat,
                                    "pickup_lng": ride.pickup_lng,
                                    "exclude_driver_ids": [],
                                },
                            )
                            tools_called_this_turn.append({"name": "check_driver_availability", "arguments": {"vehicle_type": state.vehicle_type}, "result": driver_check})
                            yield {"type": "tool_end", "name": "check_driver_availability", "result": driver_check}

                            if not driver_check.get("found"):
                                state.stage = "failed"
                                ride.status = "failed_no_driver"
                                db.commit()
                                reply_text = f"No available {state.vehicle_type} drivers were found near {state.pickup} right now. Would you like to select another vehicle type?"
                            else:
                                # Tool 2: calculate fare
                                yield {"type": "tool_start", "name": "calculate_fare", "arguments": {"pickup_lat": ride.pickup_lat, "destination_lat": ride.destination_lat, "vehicle_type": state.vehicle_type}}
                                fare_result = mcp_server.execute_tool(
                                    "calculate_fare",
                                    {
                                        "pickup_lat": ride.pickup_lat,
                                        "pickup_lng": ride.pickup_lng,
                                        "destination_lat": ride.destination_lat,
                                        "destination_lng": ride.destination_lng,
                                        "vehicle_type": state.vehicle_type,
                                    },
                                )
                                tools_called_this_turn.append({"name": "calculate_fare", "arguments": {"vehicle_type": state.vehicle_type}, "result": fare_result})
                                yield {"type": "tool_end", "name": "calculate_fare", "result": fare_result}
                                ride.fare_estimate = fare_result.get("fare", 120.0)

                                # Tool 3: assign driver
                                assigned_driver_id = driver_check["driver_id"]
                                yield {"type": "tool_start", "name": "assign_driver", "arguments": {"ride_id": ride.id, "driver_id": assigned_driver_id}}
                                assign_result = mcp_server.execute_tool("assign_driver", {"ride_id": ride.id, "driver_id": assigned_driver_id})
                                tools_called_this_turn.append({"name": "assign_driver", "arguments": {"ride_id": ride.id, "driver_id": assigned_driver_id}, "result": assign_result})
                                yield {"type": "tool_end", "name": "assign_driver", "result": assign_result}

                                if not assign_result.get("success"):
                                    # Reassign
                                    yield {"type": "tool_start", "name": "reassign_driver", "arguments": {"ride_id": ride.id, "rejected_driver_id": assigned_driver_id}}
                                    reassign_res = mcp_server.execute_tool("reassign_driver", {"ride_id": ride.id, "rejected_driver_id": assigned_driver_id})
                                    tools_called_this_turn.append({"name": "reassign_driver", "result": reassign_res})
                                    yield {"type": "tool_end", "name": "reassign_driver", "result": reassign_res}
                                    if reassign_res.get("success"):
                                        assigned_driver_id = reassign_res["new_driver"]["driver_id"]
                                    else:
                                        state.stage = "failed"
                                        ride.status = "failed_no_driver"
                                        db.commit()
                                        reply_text = "All drivers are currently occupied. Please try again in a few moments."

                                if state.stage != "failed":
                                    # Tool 4: notify user & driver
                                    yield {"type": "tool_start", "name": "notify_user_and_driver", "arguments": {"employee_id": employee.id, "driver_id": assigned_driver_id, "ride_id": ride.id}}
                                    notif_result = mcp_server.execute_tool("notify_user_and_driver", {"employee_id": employee.id, "driver_id": assigned_driver_id, "ride_id": ride.id})
                                    tools_called_this_turn.append({"name": "notify_user_and_driver", "result": notif_result})
                                    yield {"type": "tool_end", "name": "notify_user_and_driver", "result": notif_result}

                                    state.stage = "confirmed"
                                    ride.status = "confirmed"
                                    db.commit()

                                    driver = db.query(Driver).filter(Driver.id == assigned_driver_id).first()
                                    drv_name = driver.name if driver else "Driver"
                                    drv_num = driver.vehicle_number if driver else "Vehicle"
                                    eta = driver_check.get("eta_minutes", 5)
                                    fare = f"₹{round(ride.fare_estimate, 2)}"

                                    if state.channel == "call":
                                        reply_text = (
                                            f"Your ride is confirmed! Driver {drv_name} is arriving in {eta} minutes "
                                            f"in a {state.vehicle_type}, vehicle number {drv_num}. "
                                            f"Estimated fare is {fare}. Have a safe trip!"
                                        )
                                    else:
                                        reply_text = (
                                            f"🎉 Your ride is confirmed!\n"
                                            f"🚗 Driver: {drv_name} ({driver.phone_number if driver else ''})\n"
                                            f"🚘 Vehicle: {state.vehicle_type.upper()} - {drv_num}\n"
                                            f"⏱️ ETA: {eta} minutes\n"
                                            f"📍 Pickup: {state.pickup}\n"
                                            f"🏁 Destination: {state.destination}\n"
                                            f"💵 Estimated Fare: {fare}\n"
                                            f"Notifications have been dispatched."
                                        )

                # Stream response tokens
                words = reply_text.split(" ")
                for i, word in enumerate(words):
                    chunk = word + (" " if i < len(words) - 1 else "")
                    yield {"type": "token", "chunk": chunk}
                    await asyncio.sleep(0.015)

            # Record in history
            messages.append({"role": "assistant", "content": reply_text})
            state.messages_json = json.dumps(messages)
            db.commit()
            db.refresh(state)

            # Final done event
            yield {
                "type": "done",
                "session_id": session_id,
                "reply": reply_text,
                "stage": state.stage,
                "slots": {
                    "pickup": state.pickup,
                    "destination": state.destination,
                    "vehicle_type": state.vehicle_type,
                    "booking_for_self": bool(state.booking_for_self),
                },
                "ride_id": state.active_ride_id,
                "mcp_tools_called": tools_called_this_turn,
            }

        finally:
            db.close()

    def _process_with_openai(
        self,
        db: Session,
        state: ConversationState,
        ride: Ride,
        employee: Employee,
        messages: List[Dict[str, Any]],
        tools_called_this_turn: List[Dict[str, Any]],
    ) -> str:
        """Executes LLM tool-calling loop using OpenAI API."""
        from openai import OpenAI
        client = OpenAI(api_key=settings.OPENAI_API_KEY)

        system_message = {
            "role": "system",
            "content": (
                f"{get_system_prompt(state.channel, employee.name)}\n"
                f"CURRENT ACTIVE CONTEXT:\n"
                f"- Employee ID: {employee.id}\n"
                f"- Active Ride ID: {ride.id}\n"
                f"- Current Stage: {state.stage}\n"
                f"- Filled Slots: pickup='{state.pickup}', destination='{state.destination}', vehicle_type='{state.vehicle_type}'"
            ),
        }

        openai_messages = [system_message] + messages
        tools = mcp_client.get_openai_tools()

        max_iterations = 6
        iteration = 0

        while iteration < max_iterations:
            iteration += 1
            try:
                response = client.chat.completions.create(
                    model=settings.OPENAI_MODEL,
                    messages=openai_messages,
                    tools=tools,
                    tool_choice="auto",
                    temperature=0.3,
                )
            except Exception as exc:
                logger.error(f"OpenAI API Error: {exc}, falling back to rule engine.")
                return self._process_with_rule_engine(
                    db=db,
                    state=state,
                    ride=ride,
                    employee=employee,
                    user_text=messages[-1]["content"],
                    tools_called_this_turn=tools_called_this_turn,
                )

            choice = response.choices[0]
            message = choice.message

            if not message.tool_calls:
                return message.content or "How else can I assist with your ride?"

            assistant_tool_msg = {
                "role": "assistant",
                "content": message.content,
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {"name": tc.function.name, "arguments": tc.function.arguments},
                    }
                    for tc in message.tool_calls
                ],
            }
            openai_messages.append(assistant_tool_msg)

            for tool_call in message.tool_calls:
                name = tool_call.function.name
                raw_args = tool_call.function.arguments
                try:
                    args = json.loads(raw_args)
                except Exception:
                    args = {}

                if name in ("assign_driver", "reassign_driver") and "ride_id" not in args:
                    args["ride_id"] = ride.id
                if name == "notify_user_and_driver":
                    args.setdefault("ride_id", ride.id)
                    args.setdefault("employee_id", employee.id)

                tool_result = mcp_client.execute_tool_call(name, args)
                tools_called_this_turn.append({"name": name, "arguments": args, "result": tool_result})

                if name == "verify_location":
                    loc_type = args.get("location_type") or tool_result.get("location_type")
                    if tool_result.get("valid"):
                        if loc_type == "pickup" or (not state.pickup and loc_type != "destination"):
                            state.pickup = tool_result.get("formatted_address")
                            ride.pickup_address = state.pickup
                            ride.pickup_lat = tool_result.get("lat")
                            ride.pickup_lng = tool_result.get("lng")
                        else:
                            state.destination = tool_result.get("formatted_address")
                            ride.destination_address = state.destination
                            ride.destination_lat = tool_result.get("lat")
                            ride.destination_lng = tool_result.get("lng")
                        db.commit()

                elif name == "calculate_fare":
                    if "fare" in tool_result:
                        ride.fare_estimate = tool_result["fare"]
                        state.stage = "tool_calling"
                        db.commit()

                elif name == "assign_driver":
                    if tool_result.get("success"):
                        state.stage = "confirmed"
                        ride.status = "confirmed"
                        ride.driver_id = tool_result.get("driver_id")
                        db.commit()

                elif name == "reassign_driver":
                    if tool_result.get("success"):
                        state.stage = "confirmed"
                        ride.status = "confirmed"
                        db.commit()
                    elif tool_result.get("status") == "failed_no_driver":
                        state.stage = "failed"
                        ride.status = "failed_no_driver"
                        db.commit()

                openai_messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "name": name,
                    "content": json.dumps(tool_result),
                })

        return "Your ride details have been processed. Please let me know if you need anything else."

    def _process_with_rule_engine(
        self,
        db: Session,
        state: ConversationState,
        ride: Ride,
        employee: Employee,
        user_text: str,
        tools_called_this_turn: List[Dict[str, Any]],
    ) -> str:
        """
        Deterministic slot-filling state machine with robust phrase matching.
        """
        self.extract_slots(state, ride, user_text)
        db.commit()

        # 2. Stage: GATHERING
        missing_slots = []
        if not state.pickup:
            missing_slots.append("pickup location")
        if not state.destination:
            missing_slots.append("destination location")
        if not state.vehicle_type:
            missing_slots.append("vehicle type (car, bike, or auto)")

        if missing_slots:
            state.stage = "gathering"
            db.commit()
            if "pickup location" in missing_slots:
                return (
                    f"Hello {employee.name}! Where would you like to be picked up from today?"
                    if state.channel == "call"
                    else f"Hello {employee.name}! 👋 Where is your pickup location?"
                )
            elif "destination location" in missing_slots:
                return (
                    f"Got it, pickup at {state.pickup}. Where should we drop you off?"
                    if state.channel == "call"
                    else f"Pickup noted at {state.pickup}. Where is your destination?"
                )
            else:
                return (
                    "Which vehicle would you prefer? We offer car, bike, or auto."
                    if state.channel == "call"
                    else "Please choose your vehicle type: Car 🚗, Bike 🏍️, or Auto 🛺."
                )

        # 3. Stage: VERIFYING
        state.stage = "verifying"
        db.commit()

        # Verify Pickup
        v_pick = mcp_server.execute_tool("verify_location", {"address": state.pickup, "location_type": "pickup"})
        tools_called_this_turn.append({"name": "verify_location", "arguments": {"address": state.pickup, "location_type": "pickup"}, "result": v_pick})
        if not v_pick.get("valid"):
            state.pickup = None
            state.stage = "gathering"
            db.commit()
            return f"I'm sorry, I couldn't verify that pickup location: {v_pick.get('error_message')}. Could you please provide a valid landmark or address?"

        # Verify Destination
        v_dest = mcp_server.execute_tool("verify_location", {"address": state.destination, "location_type": "destination"})
        tools_called_this_turn.append({"name": "verify_location", "arguments": {"address": state.destination, "location_type": "destination"}, "result": v_dest})
        if not v_dest.get("valid"):
            state.destination = None
            state.stage = "gathering"
            db.commit()
            return f"I'm sorry, I couldn't verify that destination: {v_dest.get('error_message')}. Could you please re-specify your drop-off location?"

        # Save verified coords
        state.pickup = v_pick["formatted_address"]
        state.destination = v_dest["formatted_address"]
        ride.pickup_address = state.pickup
        ride.pickup_lat = v_pick["lat"]
        ride.pickup_lng = v_pick["lng"]
        ride.destination_address = state.destination
        ride.destination_lat = v_dest["lat"]
        ride.destination_lng = v_dest["lng"]
        ride.vehicle_type = state.vehicle_type
        db.commit()

        # 4. Stage: TOOL_CALLING
        state.stage = "tool_calling"
        db.commit()

        # Step 4.1: Check driver availability
        driver_check = mcp_server.execute_tool(
            "check_driver_availability",
            {
                "vehicle_type": state.vehicle_type,
                "pickup_lat": ride.pickup_lat,
                "pickup_lng": ride.pickup_lng,
                "exclude_driver_ids": [],
            },
        )
        tools_called_this_turn.append({
            "name": "check_driver_availability",
            "arguments": {
                "vehicle_type": state.vehicle_type,
                "pickup_lat": ride.pickup_lat,
                "pickup_lng": ride.pickup_lng,
            },
            "result": driver_check,
        })

        if not driver_check.get("found"):
            state.stage = "failed"
            ride.status = "failed_no_driver"
            db.commit()
            return f"I checked for available {state.vehicle_type} drivers near {state.pickup}, but none are available right now. Would you like to try a different vehicle type?"

        # Step 4.2: Calculate fare
        fare_result = mcp_server.execute_tool(
            "calculate_fare",
            {
                "pickup_lat": ride.pickup_lat,
                "pickup_lng": ride.pickup_lng,
                "destination_lat": ride.destination_lat,
                "destination_lng": ride.destination_lng,
                "vehicle_type": state.vehicle_type,
            },
        )
        tools_called_this_turn.append({
            "name": "calculate_fare",
            "arguments": {
                "pickup_lat": ride.pickup_lat,
                "pickup_lng": ride.pickup_lng,
                "destination_lat": ride.destination_lat,
                "destination_lng": ride.destination_lng,
                "vehicle_type": state.vehicle_type,
            },
            "result": fare_result,
        })
        ride.fare_estimate = fare_result.get("fare", 150.0)
        db.commit()

        # Step 4.3: Assign Driver
        assigned_driver_id = driver_check["driver_id"]
        assign_result = mcp_server.execute_tool(
            "assign_driver",
            {"ride_id": ride.id, "driver_id": assigned_driver_id},
        )
        tools_called_this_turn.append({
            "name": "assign_driver",
            "arguments": {"ride_id": ride.id, "driver_id": assigned_driver_id},
            "result": assign_result,
        })

        if not assign_result.get("success"):
            reassign_result = mcp_server.execute_tool(
                "reassign_driver",
                {"ride_id": ride.id, "rejected_driver_id": assigned_driver_id},
            )
            tools_called_this_turn.append({
                "name": "reassign_driver",
                "arguments": {"ride_id": ride.id, "rejected_driver_id": assigned_driver_id},
                "result": reassign_result,
            })
            if not reassign_result.get("success"):
                state.stage = "failed"
                ride.status = "failed_no_driver"
                db.commit()
                return "We could not secure a driver for your ride at this moment. Please try again in a few minutes."
            assigned_driver_id = reassign_result["new_driver"]["driver_id"]

        # Step 4.4: Notify User & Driver via MCP
        notify_result = mcp_server.execute_tool(
            "notify_user_and_driver",
            {"employee_id": employee.id, "driver_id": assigned_driver_id, "ride_id": ride.id},
        )
        tools_called_this_turn.append({
            "name": "notify_user_and_driver",
            "arguments": {"employee_id": employee.id, "driver_id": assigned_driver_id, "ride_id": ride.id},
            "result": notify_result,
        })

        # Step 5: Confirmation
        state.stage = "confirmed"
        ride.status = "confirmed"
        db.commit()

        driver = db.query(Driver).filter(Driver.id == assigned_driver_id).first()
        driver_name = driver.name if driver else "Driver"
        vehicle_num = driver.vehicle_number if driver else "Assigned vehicle"
        eta = driver_check.get("eta_minutes", 5)
        fare = f"₹{round(ride.fare_estimate, 2)}"

        if state.channel == "call":
            return (
                f"Your ride is confirmed! Driver {driver_name} is arriving in {eta} minutes "
                f"in a {state.vehicle_type}, vehicle number {vehicle_num}. "
                f"Estimated fare is {fare}. Have a safe trip!"
            )
        else:
            return (
                f"🎉 Your ride is confirmed!\n"
                f"🚗 Driver: {driver_name} ({driver.phone_number if driver else ''})\n"
                f"🚘 Vehicle: {state.vehicle_type.upper()} - {vehicle_num}\n"
                f"⏱️ ETA: {eta} minutes\n"
                f"📍 Pickup: {state.pickup}\n"
                f"🏁 Destination: {state.destination}\n"
                f"💵 Estimated Fare: {fare}\n"
                f"Notifications have been sent to your device."
            )

conversation_handler = ConversationHandler()
