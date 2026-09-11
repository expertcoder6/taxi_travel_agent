import random
from backend.db.database import SessionLocal, init_db, engine
from backend.db.models import Driver, Employee, Ride, ConversationState, Base

SAMPLE_DRIVERS = [
    # CAR DRIVERS (8)
    {"name": "Rajesh Kumar", "phone": "+919811100001", "type": "car", "number": "KA01-AB-1234", "lat": 12.9345, "lng": 77.6920, "status": "available", "rating": 4.9},
    {"name": "Amit Sharma", "phone": "+919811100002", "type": "car", "number": "KA03-CD-5678", "lat": 12.9380, "lng": 77.6980, "status": "available", "rating": 4.7},
    {"name": "Vikram Singh", "phone": "+919811100003", "type": "car", "number": "KA05-EF-9012", "lat": 12.9250, "lng": 77.6850, "status": "available", "rating": 4.8},
    {"name": "Sunil Varma", "phone": "+919811100004", "type": "car", "number": "KA51-GH-3456", "lat": 12.9716, "lng": 77.6412, "status": "on_trip", "rating": 4.6},
    {"name": "Kiran Reddy", "phone": "+919811100005", "type": "car", "number": "KA04-IJ-7890", "lat": 12.9121, "lng": 77.6446, "status": "available", "rating": 4.85},
    {"name": "Deepak Joshi", "phone": "+919811100006", "type": "car", "number": "KA02-KL-2345", "lat": 12.9900, "lng": 77.7100, "status": "offline", "rating": 4.4},
    {"name": "Rohan Deshmukh", "phone": "+919811100007", "type": "car", "number": "KA01-MN-6789", "lat": 12.9300, "lng": 77.7000, "status": "available", "rating": 4.75},
    {"name": "Farhan Akhtar", "phone": "+919811100008", "type": "car", "number": "KA03-OP-1357", "lat": 12.9450, "lng": 77.6800, "status": "available", "rating": 4.92},

    # BIKE DRIVERS (8)
    {"name": "Sanjay Gowda", "phone": "+919822200001", "type": "bike", "number": "KA03-BK-1122", "lat": 12.9350, "lng": 77.6935, "status": "available", "rating": 4.8},
    {"name": "Manoj Patil", "phone": "+919822200002", "type": "bike", "number": "KA05-BK-3344", "lat": 12.9360, "lng": 77.6960, "status": "available", "rating": 4.7},
    {"name": "Ganesh Rao", "phone": "+919822200003", "type": "bike", "number": "KA01-BK-5566", "lat": 12.9280, "lng": 77.6900, "status": "on_trip", "rating": 4.5},
    {"name": "Praveen Kumar", "phone": "+919822200004", "type": "bike", "number": "KA53-BK-7788", "lat": 12.9750, "lng": 77.6000, "status": "available", "rating": 4.9},
    {"name": "Anil Hegde", "phone": "+919822200005", "type": "bike", "number": "KA04-BK-9900", "lat": 12.9150, "lng": 77.6500, "status": "available", "rating": 4.65},
    {"name": "Naveen Babu", "phone": "+919822200006", "type": "bike", "number": "KA02-BK-2233", "lat": 12.9400, "lng": 77.7050, "status": "offline", "rating": 4.3},
    {"name": "Karthik Nair", "phone": "+919822200007", "type": "bike", "number": "KA01-BK-4455", "lat": 12.9320, "lng": 77.6910, "status": "available", "rating": 4.88},
    {"name": "Suresh Pillai", "phone": "+919822200008", "type": "bike", "number": "KA03-BK-6677", "lat": 12.9390, "lng": 77.6890, "status": "available", "rating": 4.78},

    # AUTO DRIVERS (8)
    {"name": "Manjunath K", "phone": "+919833300001", "type": "auto", "number": "KA01-AT-1001", "lat": 12.9348, "lng": 77.6940, "status": "available", "rating": 4.82},
    {"name": "Ramesh Swamy", "phone": "+919833300002", "type": "auto", "number": "KA03-AT-2002", "lat": 12.9370, "lng": 77.6975, "status": "available", "rating": 4.75},
    {"name": "Srinivas Murthy", "phone": "+919833300003", "type": "auto", "number": "KA05-AT-3003", "lat": 12.9265, "lng": 77.6880, "status": "available", "rating": 4.6},
    {"name": "Basavaraj D", "phone": "+919833300004", "type": "auto", "number": "KA02-AT-4004", "lat": 12.9800, "lng": 77.6200, "status": "on_trip", "rating": 4.45},
    {"name": "Shivanna B", "phone": "+919833300005", "type": "auto", "number": "KA04-AT-5005", "lat": 12.9180, "lng": 77.6400, "status": "available", "rating": 4.9},
    {"name": "Venkatesh R", "phone": "+919833300006", "type": "auto", "number": "KA51-AT-6006", "lat": 12.9420, "lng": 77.7120, "status": "offline", "rating": 4.35},
    {"name": "Anand Kumar", "phone": "+919833300007", "type": "auto", "number": "KA01-AT-7007", "lat": 12.9330, "lng": 77.6955, "status": "available", "rating": 4.86},
    {"name": "Prasad G", "phone": "+919833300008", "type": "auto", "number": "KA03-AT-8008", "lat": 12.9365, "lng": 77.6870, "status": "available", "rating": 4.79},
]

SAMPLE_EMPLOYEES = [
    {"name": "Sarah Connor", "phone": "+14155552671", "fcm": "fcm_token_sarah_101"},
    {"name": "Alex Mercer", "phone": "+14155553892", "fcm": "fcm_token_alex_102"},
    {"name": "Priya Raman", "phone": "+919876543210", "fcm": "fcm_token_priya_103"},
    {"name": "David Chen", "phone": "+14155557788", "fcm": "fcm_token_david_104"},
    {"name": "Aarav Mehta", "phone": "+919888877777", "fcm": "fcm_token_aarav_105"},
    {"name": "Elena Rostova", "phone": "+14155559900", "fcm": "fcm_token_elena_106"},
    {"name": "Demo Tester", "phone": "+1234567890", "fcm": "fcm_token_demo_107"},
]

def seed_database():
    init_db()
    db = SessionLocal()
    try:
        # Clear existing seed data if any for clean slate
        db.query(Driver).delete()
        db.query(Employee).delete()
        db.query(Ride).delete()
        db.query(ConversationState).delete()
        db.commit()

        # Seed drivers
        for d in SAMPLE_DRIVERS:
            driver = Driver(
                name=d["name"],
                phone_number=d["phone"],
                vehicle_type=d["type"],
                vehicle_number=d["number"],
                current_lat=d["lat"],
                current_lng=d["lng"],
                availability_status=d["status"],
                rating=d["rating"],
            )
            db.add(driver)

        # Seed employees
        for e in SAMPLE_EMPLOYEES:
            employee = Employee(
                name=e["name"],
                phone_number=e["phone"],
                fcm_token=e["fcm"],
            )
            db.add(employee)

        db.commit()
        print(f"Successfully seeded {len(SAMPLE_DRIVERS)} drivers and {len(SAMPLE_EMPLOYEES)} employees.")
    except Exception as exc:
        db.rollback()
        print(f"Error seeding database: {exc}")
        raise
    finally:
        db.close()

if __name__ == "__main__":
    seed_database()
