from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.config import settings
from backend.db.database import init_db
from backend.channels.message_adapter import router as sms_router
from backend.channels.call_adapter import router as voice_router
from backend.api.routes import router as api_router

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: ensure tables exist
    init_db()
    # Auto-seed if database is freshly created on a new deployment
    try:
        from backend.db.database import SessionLocal
        from backend.db.models import Driver
        from backend.db.seed import seed_database
        db = SessionLocal()
        try:
            if db.query(Driver).count() == 0:
                seed_database()
        finally:
            db.close()
    except Exception as e:
        print(f"Startup seed notice: {e}")
    yield
    # Shutdown

app = FastAPI(
    title=settings.APP_NAME,
    description="AI-Powered Ride Booking Platform with Voice & Message Channels via Model Context Protocol (MCP)",
    version="1.0.0",
    lifespan=lifespan,
)

# Configure CORS for Next.js frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(sms_router)
app.include_router(voice_router)
app.include_router(api_router)

@app.get("/")
def root():
    return {
        "status": "healthy",
        "service": settings.APP_NAME,
        "company": settings.COMPANY_NAME,
        "channels": ["Voice (Twilio/Groq)", "SMS/WhatsApp (Twilio)"],
        "architecture": "Model Context Protocol (MCP)",
        "docs_url": "/docs",
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=True)
