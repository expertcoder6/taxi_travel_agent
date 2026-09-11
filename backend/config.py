from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="allow",
    )

    # App
    APP_NAME: str = "AI-Powered Ride Booking Platform"
    DEBUG: bool = True
    DATABASE_URL: str = "sqlite:///./ride_booking.db"

    # AI & Speech
    OPENAI_API_KEY: Optional[str] = None
    OPENAI_MODEL: str = "gpt-4o-mini"
    GROQ_API_KEY: Optional[str] = None
    GROQ_WHISPER_MODEL: str = "whisper-large-v3"

    # Telephony (Twilio)
    TWILIO_ACCOUNT_SID: Optional[str] = None
    TWILIO_AUTH_TOKEN: Optional[str] = None
    TWILIO_PHONE_NUMBER: Optional[str] = None
    PUBLIC_WEBHOOK_URL: str = "https://acme-ride-agent.loca.lt"

    # Notifications (Firebase)
    FIREBASE_SERVICE_ACCOUNT_JSON: Optional[str] = None

    # Business Rules
    COMPANY_NAME: str = "Acme Global Technologies"
    COMPANY_LOCATION_NAME: str = "Acme Tech Park, Outer Ring Road, Bangalore"
    COMPANY_LAT: float = 12.9352
    COMPANY_LNG: float = 77.6944
    REASSIGNMENT_MAX_RETRIES: int = 3

    # Fare Matrix (Base fare + per km rate)
    FARE_RATES: dict = {
        "bike": {"base_fare": 20.0, "rate_per_km": 8.0, "min_fare": 25.0},
        "auto": {"base_fare": 30.0, "rate_per_km": 15.0, "min_fare": 40.0},
        "car": {"base_fare": 60.0, "rate_per_km": 22.0, "min_fare": 80.0},
    }

settings = Settings()
