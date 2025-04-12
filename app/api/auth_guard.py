from fastapi import Request, HTTPException
from jose import jwt
import os

from app.core.config import settings

SUPABASE_JWT_SECRET = os.getenv("SUPABASE_JWT_SECRET")
def verify_jwt(token: str):
    try:
        print(settings.SUPABASE_JWT_SECRET)
        decoded = jwt.decode(token, settings.SUPABASE_JWT_SECRET, algorithms=["HS256"])
        return decoded  # contains `sub`, `email`, etc.
    except Exception as e:
        raise HTTPException(status_code=401, detail="Invalid token")

async def auth_guard(request: Request):
    auth = request.headers.get("Authorization")
    if not auth or not auth.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Unauthorized")

    token = auth.split(" ")[1]
    user = verify_jwt(token)
    request.state.user = user
