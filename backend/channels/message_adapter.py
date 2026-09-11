from fastapi import APIRouter, Request, Form, Response
from pydantic import BaseModel
from typing import Optional, Dict, Any
from backend.agent.conversation_handler import conversation_handler

router = APIRouter(prefix="/sms", tags=["SMS Channel"])

class SimulateMessageRequest(BaseModel):
    session_id: Optional[str] = None
    phone_number: Optional[str] = "+14155552671"
    message: str

@router.post("/incoming")
async def twilio_incoming_sms(
    From: str = Form(...),
    Body: str = Form(...),
    MessageSid: Optional[str] = Form(None),
):
    """
    Twilio SMS / WhatsApp Inbound Webhook.
    Receives incoming text messages from Twilio, invokes the unified conversation handler,
    and returns TwiML <Response><Message>...</Message></Response>.
    """
    session_id = f"sms_{From.replace('+', '')}"
    result = conversation_handler.process_turn(
        session_id=session_id,
        channel="message",
        employee_phone=From,
        user_text=Body,
    )

    reply_text = result.get("reply", "We received your message.")

    # Format TwiML XML
    twiml_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Message>{reply_text}</Message>
</Response>"""

    return Response(content=twiml_content, media_type="application/xml")


@router.post("/simulate")
async def simulate_sms(payload: SimulateMessageRequest) -> Dict[str, Any]:
    """
    Local / Webhook Simulation Endpoint for Message Intake.
    Enables testing the entire slot-filling and MCP pipeline without needing a live Twilio number.
    """
    phone = (payload.phone_number or "+14155552671").strip()
    session_id = payload.session_id or f"sim_sms_{phone.replace('+', '')}"

    result = conversation_handler.process_turn(
        session_id=session_id,
        channel="message",
        employee_phone=phone,
        user_text=payload.message,
    )
    return result


@router.post("/simulate/stream")
async def simulate_sms_stream(payload: SimulateMessageRequest):
    """
    Real-time Server-Sent Events (SSE) streaming endpoint for SMS/chat simulator.
    Streams token chunks, slot updates, and tool call lifecycle events.
    """
    import json
    from fastapi.responses import StreamingResponse

    phone = (payload.phone_number or "+14155552671").strip()
    session_id = payload.session_id or f"sim_sms_{phone.replace('+', '')}"

    async def event_generator():
        async for event in conversation_handler.process_turn_stream(
            session_id=session_id,
            channel="message",
            employee_phone=phone,
            user_text=payload.message,
        ):
            yield f"data: {json.dumps(event)}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")
