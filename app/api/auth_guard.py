from fastapi import Request, HTTPException
from jose import jwt
import logging

from app.core.config import settings

# Configure logging
logger = logging.getLogger(__name__)

def verify_jwt(token: str):
    try:
        if not settings.SUPABASE_JWT_SECRET:
            logger.error("SUPABASE_JWT_SECRET is not configured")
            raise HTTPException(status_code=500, detail="Authentication service misconfigured")

        decoded = jwt.decode(token, settings.SUPABASE_JWT_SECRET, algorithms=["HS256"],options={"verify_aud": False}
                             )
        return decoded
    except jwt.JWTError as e:
        logger.warning(f"JWT validation failed: {str(e)}")
        raise HTTPException(status_code=401, detail="Invalid token")
    except Exception as e:
        logger.error(f"Unexpected error during JWT verification: {str(e)}")
        raise HTTPException(status_code=401, detail="Authentication failed")

async def auth_guard(request: Request):
    auth = request.headers.get("Authorization")
    if not auth or not auth.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Unauthorized")

    token = auth.split(" ")[1]
    user = verify_jwt(token)
    request.state.user = user
    return user