from fastapi import Request, HTTPException
from jose import jwt, JWTError
import logging

from app.core.config import settings

logger = logging.getLogger(__name__)

def verify_jwt(token: str):
    try:
        if not settings.SUPABASE_JWT_SECRET:
            logger.error("SUPABASE_JWT_SECRET is not configured")
            raise HTTPException(status_code=500, detail="Authentication service misconfigured")

        decoded = jwt.decode(token, settings.SUPABASE_JWT_SECRET, algorithms=["HS256"],options={"verify_aud": False}
                             )
        return decoded
    except JWTError as e:
        logger.warning(f"JWT validation failed: {str(e)}")
        raise HTTPException(status_code=401, detail="Invalid token")
    except Exception as e:
        logger.error(f"Unexpected error during JWT verification: {str(e)}")
        raise HTTPException(status_code=401, detail="Authentication failed")

async def auth_guard(request: Request):
    """Auth guard that requires authentication and email verification."""
    from app.services.user_service import user_service
    
    auth = request.headers.get("Authorization")
    if not auth or not auth.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Unauthorized")

    token = auth.split(" ")[1]
    user = verify_jwt(token)
    
    # Get user profile to check email verification status
    try:
        user_id = user.get("sub")
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid user session")
            
        profile = await user_service._get_basic_profile(user_id)
        
        if not profile.get("email_verified", False):
            raise HTTPException(
                status_code=403, 
                detail="Email verification required. Please check your email and verify your account before accessing this feature."
            )
            
        request.state.user = user
        return user
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error checking email verification status: {str(e)}")
        raise HTTPException(status_code=500, detail="Error validating account status")

