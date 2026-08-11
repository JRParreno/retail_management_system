"""Seed common Philippine motorcycle models.

Run:
  python -m app.scripts.seed_motorcycle_models
"""

from sqlalchemy import select

from app.db.session import SessionLocal
from app.models.motorcycle import MotorcycleModel

# Popular street / scooter / underbone models commonly seen in PH shops.
# Scooter-heavy for shops focused on automatic / CVT units.
MOTORCYCLE_MODELS: list[tuple[str, str]] = [
    # Honda scooters
    ("Honda", "Beat"),
    ("Honda", "Beat Street"),
    ("Honda", "Scoopy"),
    ("Honda", "Scoopy Prestige"),
    ("Honda", "Click 125i"),
    ("Honda", "Click 160"),
    ("Honda", "Airblade 160"),
    ("Honda", "PCX 160"),
    ("Honda", "ADV 160"),
    ("Honda", "STYLO 160"),
    ("Honda", "EM1 e:"),
    # Honda underbone / street
    ("Honda", "Wave 110"),
    ("Honda", "Wave 125 Alpha"),
    ("Honda", "XRM 125"),
    ("Honda", "TMX 125 Alpha"),
    ("Honda", "RS150R"),
    ("Honda", "CBR150R"),
    ("Honda", "CB150R"),
    ("Honda", "XR150L"),
    ("Honda", "CRF150L"),
    ("Honda", "Rebel 300"),
    # Yamaha scooters
    ("Yamaha", "Mio Sporty"),
    ("Yamaha", "Mio i 125"),
    ("Yamaha", "Mio Gear"),
    ("Yamaha", "Mio Gravis"),
    ("Yamaha", "Mio Fazzio"),
    ("Yamaha", "XMAX"),
    ("Yamaha", "NMAX"),
    ("Yamaha", "NMAX Connected"),
    ("Yamaha", "Aerox 155"),
    ("Yamaha", "Aerox Connected"),
    ("Yamaha", "Lexi"),
    ("Yamaha", "Grand Filano"),
    ("Yamaha", "Freego"),
    # Yamaha underbone / street
    ("Yamaha", "Sniper 155"),
    ("Yamaha", "MT-15"),
    ("Yamaha", "YZF-R15"),
    ("Yamaha", "XSR155"),
    ("Yamaha", "FZ-S FI"),
    ("Yamaha", "Jupiter MX"),
    ("Yamaha", "Sight"),
    ("Yamaha", "Vega Force"),
    # Suzuki scooters
    ("Suzuki", "Address"),
    ("Suzuki", "Address Playful"),
    ("Suzuki", "Burgman Street"),
    ("Suzuki", "Burgman 400"),
    ("Suzuki", "Skydrive Sport"),
    ("Suzuki", "Skydrive Crossover"),
    ("Suzuki", "Avenis 125"),
    ("Suzuki", "Let's"),
    # Suzuki underbone / street
    ("Suzuki", "Smash 115"),
    ("Suzuki", "Raider R150"),
    ("Suzuki", "GSX-R150"),
    ("Suzuki", "Gixxer 150"),
    # Kawasaki / Bajaj-badged common in PH
    ("Kawasaki", "Barako II"),
    ("Kawasaki", "CT100"),
    ("Kawasaki", "Rouser NS200"),
    ("Kawasaki", "Rouser 200NS"),
    ("Kawasaki", "Dominar 400"),
    ("Kawasaki", "KLX150"),
    ("Kawasaki", "Ninja 400"),
    ("Kawasaki", "W175"),
    # TVS scooters / street
    ("TVS", "Ntorq 125"),
    ("TVS", "Ntorq Race XP"),
    ("TVS", "Jupiter"),
    ("TVS", "Apache RTR 160"),
    ("TVS", "Apache RTR 200"),
    # Bajaj
    ("Bajaj", "Pulsar NS200"),
    ("Bajaj", "Pulsar 220F"),
    ("Bajaj", "CT 100"),
    ("Bajaj", "Avenger 220"),
    # SYM / Kymco / Vespa scooters
    ("SYM", "Bonus 110"),
    ("SYM", "Jet 14"),
    ("SYM", "VF3i 185"),
    ("SYM", "Crox"),
    ("Kymco", "Like 150"),
    ("Kymco", "Like 200i"),
    ("Kymco", "X-Town 300i"),
    ("Kymco", "Agility 125"),
    ("Vespa", "Primavera 150"),
    ("Vespa", "Sprint 150"),
    ("Vespa", "GTS 300"),
    ("Piaggio", "Medley 150"),
    ("Piaggio", "Liberty 150"),
    # Other PH-common scooters / light motorcycles
    ("Rusi", "Classic 150"),
    ("Rusi", "Mini Classic"),
    ("Skygo", "King 150"),
    ("Skygo", "Boss 150"),
    ("Keeway", "Zahara 125"),
    ("Keeway", "Fact 150"),
    ("Motorstar", "Cafe 150"),
    ("Motorstar", "Xplorer"),
    ("Loncin", "Voge"),
    ("CFMoto", "300NK"),
    ("CFMoto", "250SR"),
    ("Niu", "NQi"),
    ("Niu", "MQi"),
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
