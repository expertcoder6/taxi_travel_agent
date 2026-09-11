import io
import os
import logging
from typing import Optional, Dict, Any
from fastapi import APIRouter, Request, Form, Response, UploadFile, File
from pydantic import BaseModel

from backend.config import settings
from backend.agent.conversation_handler import conversation_handler

logger = logging.getLogger("channels.call")
router = APIRouter(prefix="/voice", tags=["Voice Channel"])

class SimulateCallRequest(BaseModel):
    session_id: Optional[str] = None
    phone_number: Optional[str] = "+14155552671"
    user_text: str

def transcribe_audio_with_groq(audio_bytes: bytes, filename: str = "audio.wav") -> str:
    """Uses Groq API Whisper model (whisper-large-v3) to transcribe spoken audio."""
    if not settings.GROQ_API_KEY or not settings.GROQ_API_KEY.strip():
        logger.warning("GROQ_API_KEY not configured. Falling back to direct text.")
        return ""

    try:
        from groq import Groq
        client = Groq(api_key=settings.GROQ_API_KEY)
        buffer = io.BytesIO(audio_bytes)
        buffer.name = filename

        transcription = client.audio.transcriptions.create(
            model=settings.GROQ_WHISPER_MODEL,
            file=buffer,
            response_format="text",
        )
        return transcription.strip() if isinstance(transcription, str) else transcription.text.strip()
    except Exception as exc:
        logger.error(f"Groq Whisper transcription failed: {exc}")
        return ""


@router.post("/inbound")
async def twilio_inbound_call(
    From: str = Form(...),
    CallSid: str = Form(...),
):
    """
    Twilio Programmable Voice Webhook (Inbound Call).
    Answers call and gathers initial speech from caller.
    """
    session_id = f"call_{CallSid}"
    greeting = (
        f"Welcome to {settings.COMPANY_NAME} Ride Booking. "
        "Where would you like to be picked up from today?"
    )

    twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Gather input="speech" action="/voice/process" method="POST" timeout="5" speechTimeout="auto" language="en-IN">
        <Say voice="Polly.Joanna-Neural">{greeting}</Say>
    </Gather>
    <Say voice="Polly.Joanna-Neural">We didn't catch that. Please call back anytime. Goodbye.</Say>
    <Hangup/>
</Response>"""

    return Response(content=twiml, media_type="application/xml")


@router.post("/process")
async def twilio_process_speech(
    From: str = Form(...),
    CallSid: str = Form(...),
    SpeechResult: Optional[str] = Form(None),
    RecordingUrl: Optional[str] = Form(None),
):
    """
    Twilio Voice Speech Callback.
    Takes caller speech (transcribed by Twilio or passed to Groq Whisper),
    invokes the conversation handler, and returns spoken TwiML response.
    """
    session_id = f"call_{CallSid}"
    caller_text = SpeechResult or ""

    # If RecordingUrl is provided from Twilio Media stream / recording, transcribe via Groq
    if RecordingUrl and settings.GROQ_API_KEY:
        try:
            import httpx
            async with httpx.AsyncClient() as client:
                resp = await client.get(RecordingUrl)
                if resp.status_code == 200:
                    whisper_text = transcribe_audio_with_groq(resp.content, "call_recording.wav")
                    if whisper_text:
                        caller_text = whisper_text
        except Exception as exc:
            logger.warning(f"Failed to fetch RecordingUrl: {exc}")

    if not caller_text.strip():
        twiml = """<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Gather input="speech" action="/voice/process" method="POST" timeout="5" speechTimeout="auto" language="en-IN">
        <Say voice="Polly.Joanna-Neural">I didn't quite hear you. Could you please repeat your pickup or destination?</Say>
    </Gather>
    <Hangup/>
</Response>"""
        return Response(content=twiml, media_type="application/xml")

    # Unified pipeline
    result = conversation_handler.process_turn(
        session_id=session_id,
        channel="call",
        employee_phone=From,
        user_text=caller_text,
    )

    reply_text = result.get("reply", "Your request is being processed.")
    stage = result.get("stage")

    if stage in ("confirmed", "failed"):
        # Complete call
        twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Joanna-Neural">{reply_text}</Say>
    <Say voice="Polly.Joanna-Neural">Thank you for choosing {settings.COMPANY_NAME}. Goodbye!</Say>
    <Hangup/>
</Response>"""
    else:
        # Continue conversational slot-filling
        twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Gather input="speech" action="/voice/process" method="POST" timeout="5" speechTimeout="auto" language="en-IN">
        <Say voice="Polly.Joanna-Neural">{reply_text}</Say>
    </Gather>
    <Say voice="Polly.Joanna-Neural">Are you still there? Please call back when you're ready.</Say>
    <Hangup/>
</Response>"""

    return Response(content=twiml, media_type="application/xml")


@router.post("/simulate")
async def simulate_call(payload: SimulateCallRequest) -> Dict[str, Any]:
    """
    Interactive Voice Simulator Endpoint.
    Simulates a voice call turn with the unified pipeline.
    """
    phone = (payload.phone_number or "+14155552671").strip()
    session_id = payload.session_id or f"sim_call_{phone.replace('+', '')}"

    result = conversation_handler.process_turn(
        session_id=session_id,
        channel="call",
        employee_phone=phone,
        user_text=payload.user_text,
    )
    return result


@router.post("/simulate/stream")
async def simulate_call_stream(payload: SimulateCallRequest):
    """
    Real-time Server-Sent Events (SSE) streaming endpoint for Voice Call simulator.
    Streams token chunks and slot updates.
    """
    import json
    from fastapi.responses import StreamingResponse

    phone = (payload.phone_number or "+14155552671").strip()
    session_id = payload.session_id or f"sim_call_{phone.replace('+', '')}"

    async def event_generator():
        async for event in conversation_handler.process_turn_stream(
            session_id=session_id,
            channel="call",
            employee_phone=phone,
            user_text=payload.user_text,
        ):
            yield f"data: {json.dumps(event)}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.post("/transcribe")
async def transcribe_audio_file(
    file: UploadFile = File(...),
) -> Dict[str, Any]:
    """
    Receives an audio recording from the web simulator and transcribes it using Groq Whisper.
    """
    contents = await file.read()
    transcription = transcribe_audio_with_groq(contents, file.filename or "speech.wav")
    return {
        "text": transcription,
        "model": settings.GROQ_WHISPER_MODEL if settings.GROQ_API_KEY else "manual_or_browser_stt",
        "has_groq": bool(settings.GROQ_API_KEY),
    }


class CallUserRequest(BaseModel):
    phone_number: str


@router.post("/call-user")
async def trigger_agent_call_user(payload: CallUserRequest) -> Dict[str, Any]:
    """
    Triggers an outbound call from the Twilio number (+12762089447)
    directly to the user's phone number. When the user answers their phone,
    they are connected to the live AI Voice Agent!
    """
    to_phone = payload.phone_number.strip()
    if not to_phone:
        return {"success": False, "error": "Phone number is required."}

    if not settings.TWILIO_ACCOUNT_SID or not settings.TWILIO_AUTH_TOKEN:
        return {"success": False, "error": "Twilio credentials not configured in .env."}

    try:
        from twilio.rest import Client
        client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
        webhook_url = f"{settings.PUBLIC_WEBHOOK_URL.rstrip('/')}/voice/inbound"
        call = client.calls.create(
            to=to_phone,
            from_=settings.TWILIO_PHONE_NUMBER,
            url=webhook_url,
        )
        logger.info(f"Outbound call placed to {to_phone} with SID {call.sid}")
        return {
            "success": True,
            "call_sid": call.sid,
            "to": to_phone,
            "message": f"Calling {to_phone}... Please pick up your phone to talk to the AI Agent!",
        }
    except Exception as exc:
        logger.error(f"Failed to trigger outbound call to {to_phone}: {exc}")
        return {"success": False, "error": str(exc)}

