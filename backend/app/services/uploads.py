from pathlib import Path

UPLOAD_DIR = Path(__file__).resolve().parents[2] / "uploads" / "payment_proofs"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
