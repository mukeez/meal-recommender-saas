from enum import Enum
import hashlib
from datetime import datetime, timedelta


class OTPTestConstants(Enum):
    """Constants for OTP data used in tests."""
    
    MOCK_OTP = "123456"
    MOCK_HASHED_OTP = hashlib.sha256("123456".encode()).hexdigest()
    MOCK_SESSION_TOKEN = "valid-session-token-abcd1234"
    MOCK_INVALID_SESSION_TOKEN = "invalid-session-token-xyz789"
    MOCK_NEW_PASSWORD = "NewSecureP@ssw0rd"


# Helper functions for test data
def get_valid_otp_entry(email):
    """Generate a valid OTP entry for testing."""
    return {
        "email": email,
        "otp_hash": OTPTestConstants.MOCK_HASHED_OTP.value,
        "expires_at": (datetime.now() + timedelta(minutes=5)).isoformat()
    }


def get_expired_otp_entry(email):
    """Generate an expired OTP entry for testing."""
    return {
        "email": email,
        "otp_hash": OTPTestConstants.MOCK_HASHED_OTP.value,
        "expires_at": (datetime.now() - timedelta(minutes=5)).isoformat()
    }


def get_session_token_entry(email):
    """Generate a session token entry for testing."""
    return {
        "email": email,
        "token": OTPTestConstants.MOCK_SESSION_TOKEN.value,
        "created_at": datetime.now().isoformat()
    }