"""Seed common Philippine motorcycle models.

Run:
  python -m app.scripts.seed_motorcycle_models
"""

from sqlalchemy import select

from app.db.session import SessionLocal
from app.models.motorcycle import MotorcycleModel

# Popular street / scooter / underbone models commonly seen in PH shops.
MOTORCYCLE_MODELS: list[tuple[str, str]] = [
    # Honda
    ("Honda", "Click 125i"),
    ("Honda", "Click 160"),
    ("Honda", "Beat"),
    ("Honda", "Scoopy"),
    ("Honda", "PCX 160"),
    ("Honda", "ADV 160"),
    ("Honda", "Airblade 160"),
    ("Honda", "Wave 125 Alpha"),
    ("Honda", "RS150R"),
    ("Honda", "XR150L"),
    ("Honda", "CRF150L"),
    ("Honda", "TMX 125 Alpha"),
    ("Honda", "XRM 125"),
    ("Honda", "Rebel 300"),
    ("Honda", "CB150R"),
    ("Honda", "CBR150R"),
    # Yamaha
    ("Yamaha", "Mio i 125"),
    ("Yamaha", "Mio Sporty"),
    ("Yamaha", "Mio Gear"),
    ("Yamaha", "NMAX"),
    ("Yamaha", "Aerox 155"),
    ("Yamaha", "Sniper 155"),
    ("Yamaha", "MT-15"),
    ("Yamaha", "YZF-R15"),
    ("Yamaha", "XSR155"),
    ("Yamaha", "FZ-S FI"),
    ("Yamaha", "Jupiter MX"),
    ("Yamaha", "Sight"),
    ("Yamaha", "Vega Force"),
    # Suzuki
    ("Suzuki", "Smash 115"),
    ("Suzuki", "Raider R150"),
    ("Suzuki", "Burgman Street"),
    ("Suzuki", "Address"),
    ("Suzuki", "GSX-R150"),
    ("Suzuki", "Gixxer 150"),
    ("Suzuki", "Skydrive Sport"),
    ("Suzuki", "Burgman 400"),
    # Kawasaki
    ("Kawasaki", "Barako II"),
    ("Kawasaki", "Rouser NS200"),
    ("Kawasaki", "Rouser 200NS"),
    ("Kawasaki", "Dominar 400"),
    ("Kawasaki", "CT100"),
    ("Kawasaki", "KLX150"),
    ("Kawasaki", "Ninja 400"),
    ("Kawasaki", "W175"),
    # TVS / Bajaj / others common in PH
    ("TVS", "Ntorq 125"),
    ("TVS", "Apache RTR 160"),
    ("TVS", "Apache RTR 200"),
    ("Bajaj", "Pulsar NS200"),
    ("Bajaj", "Pulsar 220F"),
    ("Bajaj", "CT 100"),
    ("SYM", "Bonus 110"),
    ("SYM", "VF3i 185"),
    ("Kymco", "Like 150"),
    ("Kymco", "X-Town 300i"),
    ("Vespa", "Primavera 150"),
    ("Vespa", "Sprint 150"),
    ("Rusi", "Classic 150"),
    ("Skygo", "King 150"),
]


def seed_motorcycle_models() -> int:
    db = SessionLocal()
    created = 0
    try:
        for brand, name in MOTORCYCLE_MODELS:
            exists = db.scalar(
                select(MotorcycleModel).where(
                    MotorcycleModel.brand == brand,
                    MotorcycleModel.name == name,
                )
            )
            if exists is None:
                db.add(MotorcycleModel(brand=brand, name=name, is_active=True))
                created += 1
                print(f"Created motorcycle model: {brand} {name}")
        db.commit()
        print(f"Motorcycle model seed complete ({created} new).")
        return created
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed_motorcycle_models()
