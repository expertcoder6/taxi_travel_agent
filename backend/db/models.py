from datetime import datetime
from sqlalchemy import (
    Column,
    Integer,
    String,
    Float,
    DateTime,
    ForeignKey,
    CheckConstraint,
    Text,
)
from sqlalchemy.orm import relationship, declarative_base

Base = declarative_base()

class Driver(Base):
    __tablename__ = "drivers"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False)
    phone_number = Column(String(20), nullable=False)
    vehicle_type = Column(String(20), nullable=False)
    vehicle_number = Column(String(50), nullable=True)
    current_lat = Column(Float, nullable=True)
    current_lng = Column(Float, nullable=True)
    availability_status = Column(String(20), nullable=False, default="available")
    rating = Column(Float, default=4.5)
    created_at = Column(DateTime, default=datetime.utcnow)

    rides = relationship("Ride", back_populates="driver")

    __table_args__ = (
        CheckConstraint("vehicle_type IN ('car','bike','auto')", name="check_vehicle_type"),
        CheckConstraint("availability_status IN ('available','on_trip','offline')", name="check_availability_status"),
    )

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "phone_number": self.phone_number,
            "vehicle_type": self.vehicle_type,
            "vehicle_number": self.vehicle_number,
            "current_lat": self.current_lat,
            "current_lng": self.current_lng,
            "availability_status": self.availability_status,
            "rating": round(self.rating, 2) if self.rating else 4.5,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class Employee(Base):
    __tablename__ = "employees"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False)
    phone_number = Column(String(20), unique=True, nullable=False)
    fcm_token = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    rides = relationship("Ride", back_populates="employee")

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "phone_number": self.phone_number,
            "fcm_token": self.fcm_token,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class Ride(Base):
    __tablename__ = "rides"

    id = Column(Integer, primary_key=True, autoincrement=True)
    employee_id = Column(Integer, ForeignKey("employees.id"), nullable=True)
    driver_id = Column(Integer, ForeignKey("drivers.id"), nullable=True)
    pickup_address = Column(String(255), nullable=True)
    pickup_lat = Column(Float, nullable=True)
    pickup_lng = Column(Float, nullable=True)
    destination_address = Column(String(255), nullable=True)
    destination_lat = Column(Float, nullable=True)
    destination_lng = Column(Float, nullable=True)
    vehicle_type = Column(String(20), nullable=True)
    passenger_count = Column(Integer, default=1)
    scheduled_time = Column(String(100), default="Immediate")
    requested_driver = Column(String(100), nullable=True)
    fare_estimate = Column(Float, nullable=True)
    status = Column(String(30), default="pending")
    channel = Column(String(20), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    employee = relationship("Employee", back_populates="rides")
    driver = relationship("Driver", back_populates="rides")

    __table_args__ = (
        CheckConstraint(
            "status IN ('pending','confirmed','in_progress','completed','cancelled','failed_no_driver',"
            "'booked','driver_assigned','driver_accepted','driver_arriving','ride_started','ride_completed')",
            name="check_ride_status",
        ),
        CheckConstraint("channel IN ('call','message')", name="check_ride_channel"),
    )

    def to_dict(self):
        return {
            "id": self.id,
            "employee_id": self.employee_id,
            "employee_name": self.employee.name if self.employee else "Guest Caller",
            "employee_phone": self.employee.phone_number if self.employee else None,
            "driver_id": self.driver_id,
            "driver_name": self.driver.name if self.driver else None,
            "driver_phone": self.driver.phone_number if self.driver else None,
            "vehicle_number": self.driver.vehicle_number if self.driver else None,
            "requested_driver": self.requested_driver,
            "pickup_address": self.pickup_address,
            "pickup_lat": self.pickup_lat,
            "pickup_lng": self.pickup_lng,
            "destination_address": self.destination_address,
            "destination_lat": self.destination_lat,
            "destination_lng": self.destination_lng,
            "vehicle_type": self.vehicle_type,
            "passenger_count": self.passenger_count or 1,
            "scheduled_time": self.scheduled_time or "Immediate",
            "fare_estimate": round(self.fare_estimate, 2) if self.fare_estimate else None,
            "status": self.status,
            "channel": self.channel,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class ConversationState(Base):
    __tablename__ = "conversation_state"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String(100), unique=True, nullable=False)
    channel = Column(String(20), nullable=True)
    employee_phone = Column(String(20), nullable=True)
    pickup = Column(String(255), nullable=True)
    destination = Column(String(255), nullable=True)
    vehicle_type = Column(String(20), nullable=True)
    passenger_count = Column(Integer, default=1)
    scheduled_time = Column(String(100), default="Immediate")
    requested_driver = Column(String(100), nullable=True)
    booking_for_self = Column(Integer, default=1)
    stage = Column(String(30), default="gathering")
    active_ride_id = Column(Integer, nullable=True)
    messages_json = Column(Text, nullable=True, default="[]")
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        CheckConstraint(
            "stage IN ('gathering','verifying','tool_calling','confirmed','failed')",
            name="check_conversation_stage",
        ),
    )

    def to_dict(self):
        return {
            "id": self.id,
            "session_id": self.session_id,
            "channel": self.channel,
            "employee_phone": self.employee_phone,
            "pickup": self.pickup,
            "destination": self.destination,
            "vehicle_type": self.vehicle_type,
            "passenger_count": self.passenger_count or 1,
            "scheduled_time": self.scheduled_time or "Immediate",
            "requested_driver": self.requested_driver,
            "booking_for_self": bool(self.booking_for_self),
            "stage": self.stage,
            "active_ride_id": self.active_ride_id,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
