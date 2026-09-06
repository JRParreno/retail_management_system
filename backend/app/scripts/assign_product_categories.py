"""Assign product categories by matching product titles to category names.

Matching strategy (highest score wins):
1. Category name appears as a substring of the product title (case-insensitive)
2. Optional alias keywords (e.g. \"air filter\" → Filter, \"brake pad\" → Brakes)
3. Longer matches beat shorter ones (\"Belt honda\" beats \"Belt\" if both existed)

By default only products with no category are considered, and nothing is written
until you pass --apply.

Dry-run (preview):
  python -m app.scripts.assign_product_categories

Apply changes:
  python -m app.scripts.assign_product_categories --apply

Options:
  --limit N           Only process first N uncategorized products
  --include-assigned  Also re-evaluate products that already have a category
                      (only updates when a match is found)
"""

from __future__ import annotations

import argparse
import re
from collections import Counter

from sqlalchemy import select

from app.db.session import SessionLocal
from app.models.product import Product, ProductCategory

# Extra keyword -> category name (existing or auto-created).
# Prefer specific phrases; longer aliases are tried first.
CATEGORY_ALIASES: list[tuple[str, str]] = [
    ("air filter", "Filter"),
    ("oil filter", "Filter"),
    ("brake fluid", "Brakes"),
    ("brake cable", "Brakes"),
    ("brake pad", "Brakes"),
    ("breakpad", "Brakes"),
    ("break pad", "Brakes"),
    ("breakshoe", "Breakshoe"),
    ("break shoe", "Breakshoe"),
    ("spark plug", "Sparkplug"),
    ("sparkplug", "Sparkplug"),
    ("head light", "Headlight Led"),
    ("headlight", "Headlight Led"),
    ("tail light", "Tailight Led"),
    ("taillight", "Tailight Led"),
    ("tailight", "Tailight Led"),
    ("park light", "Parklight"),
    ("side mirror", "Side mirror"),
    ("rear shock", "Rear shock"),
    ("front shock", "Front Shock"),
    ("handle grip", "Handle Grip"),
    ("hand grip", "Handle Grip"),
    ("bar end", "Bar end"),
    ("ball race", "Ball race"),
    ("cvt set", "CVT SET"),
    ("torsion control", "CVT"),
    ("senlo", "MDL"),
    ("clutch lining", "clutch lining"),
    ("clutch spring", "Clutch spring"),
    ("center spring", "Center spring"),
    ("cylinder block", "Cylinder block"),
    ("ignition switch", "Ignition switch"),
    ("ckp sensor", "CKP sensor"),
    ("tps sensor", "TPS sensor"),
    ("repair kit", "Repair kit"),
    ("yamaha belt", "Belt"),
    ("faitho belt", "Belt"),
    ("belt honda", "Belt"),
    ("engine oil", "Oils"),
    ("gear oil", "Oils"),
    ("motor oil", "Oils"),
    ("honda oil", "Oils"),
    ("motul oil", "Oils"),
    ("shell advance", "Oils"),
    ("rc 19 oil", "Oils"),
    ("rc19 oil", "Oils"),
    ("shampoo", "Wax"),
    ("cnc bolts", "Bolts"),
    ("cnc bolt", "Bolts"),
    ("titanium bolts", "Bolts"),
    ("gold bolts", "Bolts"),
    ("bolts", "Bolts"),
    ("2pat bracket", "Bracket"),
    ("4pat bracket", "Bracket"),
    ("bracket", "Bracket"),
    ("axle cnc", "Axle"),
    ("axle", "Axle"),
    ("caliper", "Brakes"),
    ("center stand", "Center Stand"),
    ("side stand", "Center Stand"),
    ("crank case", "Crank Case"),
    ("drain plug", "Drain Plug"),
    ("dran plug", "Drain Plug"),
    ("engine support", "Engine Support"),
    ("exhaust pipe", "Exhaust"),
    ("fuel cock", "Fuel Cock"),
    ("handle switch", "Handle Switch"),
    ("rotor disc", "Rotor Disc"),
    ("rotor big disc", "Rotor Disc"),
    ("big disc", "Rotor Disc"),
    ("spyker disc", "Rotor Disc"),
    ("swing arm", "Swing Arm"),
    ("samco hose", "Hose"),
    ("hose set", "Hose"),
    ("seat cover", "Seat Cover"),
    ("speedometer cable", "Speedometer Cable"),
    ("throttle cable", "Throttle Cable"),
    ("throttlecable", "Throttle Cable"),
    ("pully set", "Pulley"),
    ("pully washer", "Pulley"),
    ("pully", "Pulley"),
    ("pulley", "Pulley"),
    ("flyyball", "Flyball"),
    ("flyball", "Flyball"),
    ("radiator", "Radiator"),
    ("stabilizer", "Stabilizer"),
    ("hook motor", "Hook"),
    ("euro grip", "Tires"),
    ("maxxis", "Tires"),
    ("tire", "Tires"),
    ("tyre", "Tires"),
    ("chain", "Chain"),
    ("mags", "Mags"),
    ("hub", "Hub"),
    ("lever", "Lever"),
    ("tps", "TPS sensor"),
]


# Categories that may be auto-created when an alias needs them.
AUTO_CREATE_CATEGORIES = (
    "Bolts",
    "Bracket",
    "Axle",
    "Center Stand",
    "Chain",
    "Crank Case",
    "Drain Plug",
    "Engine Support",
    "Exhaust",
    "Front Shock",
    "Fuel Cock",
    "Handle Switch",
    "Hub",
    "Hook",
    "Mags",
    "Lever",
    "Tires",
    "Radiator",
    "Rotor Disc",
    "Swing Arm",
    "Hose",
    "Seat Cover",
    "Speedometer Cable",
    "Throttle Cable",
    "Pulley",
    "Stabilizer",
    "Belt",
    "CVT",
    "MDL",
)


def _normalize(text: str) -> str:
    text = text.casefold().strip()
    text = text.replace("\\", "/")
    text = re.sub(r"[^a-z0-9/#+\s.-]+", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _ensure_alias_categories(
    db,
    *,
    apply: bool,
    categories: list[ProductCategory],
    category_by_key: dict[str, ProductCategory],
) -> None:
    """Create missing alias-target categories (e.g. Bolts) when needed."""
    needed = {target for _, target in CATEGORY_ALIASES}
    for name in sorted(needed | set(AUTO_CREATE_CATEGORIES)):
        key = _normalize(name)
        if key in category_by_key:
            continue
        if name not in AUTO_CREATE_CATEGORIES:
            print(f'Warning: alias target category "{name}" is missing')
            continue
        if apply:
            category = ProductCategory(name=name)
            db.add(category)
            db.flush()
            categories.append(category)
            category_by_key[key] = category
            print(f'Created category "{name}"')
        else:
            # Dry-run: attach an unsaved object so matching still works in the report.
            category = ProductCategory(name=name)
            categories.append(category)
            category_by_key[key] = category
            print(f'Would create category "{name}"')


def _best_match(
    product_name: str,
    categories: list[ProductCategory],
    category_by_key: dict[str, ProductCategory],
) -> tuple[ProductCategory | None, str]:
    """Return (category, reason) or (None, '')."""
    haystack = _normalize(product_name)
    if not haystack:
        return None, ""

    best: ProductCategory | None = None
    best_score = 0
    best_reason = ""

    for category in categories:
        needle = _normalize(category.name)
        if len(needle) < 2:
            continue
        if needle in haystack:
            score = len(needle)
            if score > best_score:
                best = category
                best_score = score
                best_reason = f'title contains "{category.name}"'

    # Aliases: longer phrases first. Short tokens need a word boundary.
    for alias, category_name in sorted(
        CATEGORY_ALIASES, key=lambda pair: len(pair[0]), reverse=True
    ):
        alias_key = _normalize(alias)
        if len(alias_key) < 2:
            continue
        if len(alias_key) <= 4:
            if not re.search(rf"(^|[^a-z0-9]){re.escape(alias_key)}([^a-z0-9]|$)", haystack):
                continue
        elif alias_key not in haystack:
            continue
        category = category_by_key.get(_normalize(category_name))
        if category is None:
            continue
        score = len(alias_key)
        if score > best_score:
            best = category
            best_score = score
            best_reason = f'alias "{alias}" -> {category.name}'

    return best, best_reason


def run(*, apply: bool, limit: int | None, include_assigned: bool) -> None:
    db = SessionLocal()
    try:
        categories = list(
            db.scalars(select(ProductCategory).order_by(ProductCategory.name)).all()
        )
        if not categories:
            print("No categories in the database - create some first.")
            return

        category_by_key = {_normalize(c.name): c for c in categories}
        _ensure_alias_categories(
            db, apply=apply, categories=categories, category_by_key=category_by_key
        )

        stmt = select(Product).where(Product.deleted_at.is_(None)).order_by(Product.name)
        if not include_assigned:
            stmt = stmt.where(Product.category_id.is_(None))
        products = list(db.scalars(stmt).all())
        if limit is not None:
            products = products[:limit]

        matched = 0
        unchanged = 0
        unmatched: list[str] = []
        assigned_counts: Counter[str] = Counter()

        print(
            f"Scanning {len(products)} product(s) "
            f"({'all' if include_assigned else 'uncategorized only'}) "
            f"- {'APPLY' if apply else 'DRY-RUN'}"
        )
        print("-" * 72)

        for product in products:
            category, reason = _best_match(product.name, categories, category_by_key)
            if category is None:
                unmatched.append(product.name)
                continue
            if (
                product.category_id is not None
                and category.id is not None
                and product.category_id == category.id
            ):
                unchanged += 1
                continue

            previous = None
            if product.category_id is not None:
                previous = next(
                    (c for c in categories if c.id == product.category_id),
                    None,
                )
            prev_label = previous.name if previous else "(none)"
            print(
                f"{product.name}\n"
                f"  {prev_label} -> {category.name}  [{reason}]"
            )
            matched += 1
            assigned_counts[category.name] += 1
            if apply:
                product.category_id = category.id

        if apply and matched:
            db.commit()
            print("-" * 72)
            print(f"Committed {matched} update(s).")
        elif apply:
            print("-" * 72)
            print("Nothing to commit.")
        else:
            print("-" * 72)
            print("Dry-run only - re-run with --apply to save changes.")

        print()
        print(f"Would assign / assigned: {matched}")
        print(f"Already correct:         {unchanged}")
        print(f"No match:                {len(unmatched)}")
        if assigned_counts:
            print("\nBy category:")
            for name, count in assigned_counts.most_common():
                print(f"  {count:4d}  {name}")
        if unmatched:
            print("\nUnmatched titles (first 40):")
            for name in unmatched[:40]:
                print(f"  - {name}")
            if len(unmatched) > 40:
                print(f"  ... and {len(unmatched) - 40} more")
    finally:
        db.close()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Match product titles to categories and assign them."
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Write category_id changes to the database (default is dry-run)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Only process the first N products",
    )
    parser.add_argument(
        "--include-assigned",
        action="store_true",
        help="Also consider products that already have a category",
    )
    args = parser.parse_args()
    run(
        apply=args.apply,
        limit=args.limit,
        include_assigned=args.include_assigned,
    )


if __name__ == "__main__":
    main()
