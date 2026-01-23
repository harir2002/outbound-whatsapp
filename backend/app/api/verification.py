"""
Phone Number Verification API
Verify phone numbers before making calls (required for Twilio trial accounts)
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from datetime import datetime, timedelta
import random
import string

from app.core.logging import logger
from app.core.config import settings

router = APIRouter()

# In-memory storage for verification codes (in production, use Redis or DB)
verification_codes = {}
verified_numbers = set()


class SendVerificationRequest(BaseModel):
    """Send verification code request"""
    phone_number: str


class VerifyCodeRequest(BaseModel):
    """Verify code request"""
    phone_number: str
    code: str


def generate_verification_code() -> str:
    """Generate a 6-digit verification code"""
    return ''.join(random.choices(string.digits, k=6))


@router.post("/send-code")
async def send_verification_code(request: SendVerificationRequest):
    """
    Send verification code via SMS
    
    Args:
        request: Phone number to verify
    
    Returns:
        Success message
    """
    try:
        phone_number = request.phone_number.strip()
        
        # Validate phone number format
        if not phone_number.startswith('+'):
            raise HTTPException(status_code=400, detail="Phone number must start with + and country code")
        
        # Generate verification code
        code = generate_verification_code()
        
        # Store code with expiration (5 minutes)
        verification_codes[phone_number] = {
            "code": code,
            "expires_at": datetime.utcnow() + timedelta(minutes=5),
            "attempts": 0
        }
        
        # Send SMS via Twilio
        from twilio.rest import Client
        
        client = Client(
            settings.TWILIO_ACCOUNT_SID,
            settings.TWILIO_AUTH_TOKEN
        )
        
        message_body = f"Your BFSI AI Platform verification code is: {code}\n\nThis code will expire in 5 minutes.\n\nIf you didn't request this, please ignore this message."
        
        message = client.messages.create(
            to=phone_number,
            from_=settings.TWILIO_PHONE_NUMBER,
            body=message_body
        )
        
        logger.info(f"✅ Verification code sent to {phone_number}")
        logger.info(f"   Twilio Message SID: {message.sid}")
        
        return {
            "success": True,
            "message": "Verification code sent successfully",
            "expires_in_minutes": 5,
            # For development/testing, include code (REMOVE IN PRODUCTION!)
            "debug_code": code if settings.DEBUG else None
        }
        
    except Exception as e:
        logger.error(f"❌ Failed to send verification code: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to send verification code: {str(e)}")


@router.post("/verify-code")
async def verify_code(request: VerifyCodeRequest):
    """
    Verify the code sent to phone number
    
    Args:
        request: Phone number and verification code
    
    Returns:
        Verification result
    """
    try:
        phone_number = request.phone_number.strip()
        code = request.code.strip()
        
        # Check if code exists
        if phone_number not in verification_codes:
            raise HTTPException(status_code=404, detail="No verification code found for this number")
        
        stored_data = verification_codes[phone_number]
        
        # Check if code expired
        if datetime.utcnow() > stored_data["expires_at"]:
            del verification_codes[phone_number]
            raise HTTPException(status_code=400, detail="Verification code has expired. Please request a new one.")
        
        # Check attempts
        if stored_data["attempts"] >= 3:
            del verification_codes[phone_number]
            raise HTTPException(status_code=400, detail="Too many incorrect attempts. Please request a new code.")
        
        # Verify code
        if code != stored_data["code"]:
            stored_data["attempts"] += 1
            remaining = 3 - stored_data["attempts"]
            raise HTTPException(
                status_code=400, 
                detail=f"Invalid verification code. {remaining} attempts remaining."
            )
        
        # Success! Mark number as verified
        verified_numbers.add(phone_number)
        del verification_codes[phone_number]
        
        logger.info(f"✅ Phone number verified: {phone_number}")
        
        return {
            "success": True,
            "message": "Phone number verified successfully!",
            "phone_number": phone_number,
            "verified_at": datetime.utcnow().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Verification failed: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/check/{phone_number}")
async def check_verification_status(phone_number: str):
    """
    Check if a phone number is verified
    
    Args:
        phone_number: Phone number to check
    
    Returns:
        Verification status
    """
    is_verified = phone_number in verified_numbers
    
    return {
        "success": True,
        "phone_number": phone_number,
        "is_verified": is_verified,
        "message": "Number is verified" if is_verified else "Number not verified"
    }


@router.get("/verified-numbers")
async def get_verified_numbers():
    """
    Get list of all verified numbers (for admin/testing)
    
    Returns:
        List of verified numbers
    """
    return {
        "success": True,
        "verified_numbers": list(verified_numbers),
        "count": len(verified_numbers)
    }


@router.delete("/reset/{phone_number}")
async def reset_verification(phone_number: str):
    """
    Reset verification for a phone number (for testing)
    
    Args:
        phone_number: Phone number to reset
    
    Returns:
        Success message
    """
    if phone_number in verified_numbers:
        verified_numbers.remove(phone_number)
    
    if phone_number in verification_codes:
        del verification_codes[phone_number]
    
    return {
        "success": True,
        "message": f"Verification reset for {phone_number}"
    }
