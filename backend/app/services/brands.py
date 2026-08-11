"""Product brand catalog helpers."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.product import ProductBrand

DEFAULT_SEED_BRANDS = [
    # Generic / house
    "OEM",
    "Generic",
    # Scooter & motorcycle OEMs (PH / ASEAN common)
    "Honda",
    "Yamaha",
    "Suzuki",
    "Kawasaki",
    "SYM",
    "Kymco",
    "Vespa",
    "Piaggio",
    "Aprilia",
    "TVS",
    "Bajaj",
    "Hero",
    "Keeway",
    "Rusi",
    "Motorstar",
    "Skygo",
    "Loncin",
    "Zongshen",
    "Benelli",
    "CFMoto",
    "BMW",
    "Peugeot",
    "Niu",
    # Oils & fluids
    "Motul",
    "Castrol",
    "Shell",
    "Total",
    "Elf",
    "Repsol",
    "Liqui Moly",
    "Mobil",
    "Idemitsu",
    "Valvoline",
    "Petron",
    "Caltex",
    "Prestone",
    # Ignition / electrics / bulbs
    "NGK",
    "Denso",
    "Bosch",
    "Philips",
    "Osram",
    "Yuasa",
    "GS Yuasa",
    "Motolite",
    "Furukawa",
    # Filters & intake
    "K&N",
    "HKS",
    # Brakes
    "Brembo",
    "Nissin",
    "EBC",
    "SBS",
    "RCB",
    # Drive / CVT / chain (scooters rely on belts)
    "DID",
    "RK",
    "Dayco",
    "Gates",
    "Contitech",
    "Exedy",
    "FCC",
    "Athena",
    # Tires & wheels (premium + PH budget favorites)
    "Michelin",
    "Bridgestone",
    "IRC",
    "FDR",
    "Maxxis",
    "Pirelli",
    "Dunlop",
    "Continental",
    "Swallow",
    "Chao Yang",
    "Beast",
    "Aspira",
    "Corsa",
    "Timsun",
    "Camel",
    "Deestone",
    "CST",
    "Cheng Shin",
    "Duro",
    "Zeneos",
    "Mizzle",
    "Kingland",
    "Accel",
    "Sportrim",
    # Suspension
    "YSS",
    "Ohlins",
    "Showa",
    "KYB",
    # Scooter performance / exhaust / tuning
    "Malossi",
    "Polini",
    "Stage6",
    "Doppler",
    "Tecnigas",
    "LeoVince",
    "Arrow",
    "Yoshimura",
    "Akrapovic",
    "Kitaco",
    "SP Takegawa",
    "Koso",
    "Top Performances",
    "Uma Racing",
    "TDR",
    "Bpro",
    "SSS",
    "Power1",
    "Frando",
    # Body / storage / riding gear
    "Givi",
    "SHAD",
    "Kappa",
    "Arai",
    "Shoei",
    "AGV",
    "HJC",
    "MT Helmets",
    "Nolan",
    # Budget helmets & riding gear (PH common)
    "NHK",
    "KYT",
    "JPX",
    "MDS",
    "Index",
    "INK",
    "BMC",
    "Nexx",
    "LS2",
    # Budget accessories / mirrors / grips / locks / mounts
    "Motowolf",
    "Daytona",
    "OSP",
    "KTC",
    "JVT",
    "Knight",
    "Posh",
    "GLM",
    "Moto1",
    "Rizoma",
    "Magazi",
    "KiWAV",
    "CRG",
    "Progrip",
    "Domino",
    "Renthal",
    "Kryptonite",
    "Abus",
    "Master Lock",
    "Grip Lock",
    "Xena",
    # Consumables / shop supplies
    "3M",
    "Loctite",
    "WD-40",
    "Wurth",
    "STP",
    "Turtle Wax",
    "Meguiar's",
    "Mutant",
]


def ensure_product_brand(db: Session, name: str | None) -> ProductBrand | None:
    """Upsert a brand name into the catalog. Returns None when name is empty."""
    if name is None:
        return None
    cleaned = name.strip()
    if not cleaned:
        return None
    cleaned = cleaned[:100]
    existing = db.scalar(
        select(ProductBrand).where(func.lower(ProductBrand.name) == cleaned.casefold())
    )
    if existing is not None:
        return existing
    brand = ProductBrand(name=cleaned)
    db.add(brand)
    db.flush()
    return brand


def list_brand_names(db: Session) -> list[str]:
    return list(
        db.scalars(select(ProductBrand.name).order_by(ProductBrand.name.asc())).all()
    )


def seed_default_brands(db: Session) -> int:
    """Insert default brands if missing. Returns count of newly created rows."""
    created = 0
    for name in DEFAULT_SEED_BRANDS:
        existing = db.scalar(
            select(ProductBrand.id).where(
                func.lower(ProductBrand.name) == name.casefold()
            )
        )
        if existing is None:
            db.add(ProductBrand(name=name))
            created += 1
    if created:
        db.flush()
    return created
