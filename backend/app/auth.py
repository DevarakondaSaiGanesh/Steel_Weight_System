import os
import secrets
import string
import bcrypt
from fastapi import Request, HTTPException, Depends
from sqlalchemy.orm import Session
from .database import get_db
from .models import User

SESSION_SECRET = os.environ.get("SESSION_SECRET", "dev-secret-change-me")

ALPHABET = string.ascii_letters + string.digits

MATERIALS = [
    "MS Plate", "MS Flat Bar", "Rod", "Bracket", "MS Pipe", "Angle",
    "Flange", "Bends", "Stringer", "Bollard", "Ladder", "Eye Pad",
]

ROUND_MATERIALS = {"Rod", "MS Pipe"}

DENSITY = 7850


def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode(), hashed.encode())
    except Exception:
        return False


def generate_password(length: int = 12) -> str:
    return "".join(secrets.choice(ALPHABET) for _ in range(length))


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User | None:
    user_id = request.session.get("user_id")
    if not user_id:
        return None
    return db.query(User).filter(User.id == user_id).first()


def require_user(request: Request, db: Session = Depends(get_db)) -> User:
    user = get_current_user(request, db)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return user


def require_admin(user: User = Depends(require_user)) -> User:
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin only")
    return user


def require_not_first_login(user: User = Depends(require_user)) -> User:
    if user.first_login:
        raise HTTPException(status_code=403, detail="Password change required")
    return user


def compute_weight_kg(material: str, length: float, qty: int,
                      width: float | None, thickness: float | None,
                      diameter: float | None) -> float:
    import math
    if material in ROUND_MATERIALS:
        d = diameter or 0
        return (math.pi * d * d / 4) * length * DENSITY * qty / 1_000_000_000
    w = width or 0
    t = thickness or 0
    return (length * w * t * DENSITY * qty) / 1_000_000_000
