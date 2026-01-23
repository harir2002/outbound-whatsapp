"""
Voice AI API Endpoints
Outbound voice calls using Twilio Voice API
"""

from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
import uuid

from app.services.sarvam_service import sarvam_service
from app.services.groq_service import groq_service
from app.core.logging import logger, audit_log
from app.core.security import ConsentManager, get_call_recording_disclosure

router = APIRouter()


# ==================== REQUEST MODELS ====================

class OutboundCallRequest(BaseModel):
    """Outbound call request"""
    phone_number: str
    purpose: str  # emi_reminder, policy_renewal, loan_offer, claim_update
    sector: str = "banking"
    language: str = "en"
    customer_data: dict = {}
    public_url: Optional[str] = None


class VoiceQueryRequest(BaseModel):
    """Voice query request"""
    text: str
    sector: str = "banking"
    language: str = "en"
    session_id: Optional[str] = None


# ==================== CALL SESSIONS ====================

call_sessions = {}


# ==================== ENDPOINTS ====================

@router.post("/outbound")
async def initiate_outbound_call(request: OutboundCallRequest):
    """
    Initiate outbound voice call using Twilio Voice API
    
    Args:
        request: Outbound call request
    
    Returns:
        Call details
    """
    try:
        logger.info(f"🔵 Initiating REAL voice call to {request.phone_number}")
        
        # Check consent
        if not ConsentManager.check_consent(request.phone_number, "outbound_call"):
            logger.warning(f"No outbound call consent for {request.phone_number}")
            ConsentManager.record_consent(
                user_id=request.phone_number,
                consent_type="outbound_call",
                granted=False
            )
        
        # Create call session
        call_id = str(uuid.uuid4())
        call_sessions[call_id] = {
            "call_id": call_id,
            "phone_number": request.phone_number,
            "purpose": request.purpose,
            "sector": request.sector,
            "language": request.language,
            "customer_data": request.customer_data,
            "status": "initiated",
            "created_at": datetime.utcnow().isoformat(),
            "messages": [],
            "public_url": request.public_url
        }
        
        # Generate initial greeting
        greeting = await _generate_call_greeting(request)
        logger.info(f"📝 Generated greeting: {greeting[:100]}...")
        
        # Convert to speech using SARVAM AI (High Quality)
        logger.info(f"🎙️ Generating Sarvam AI high-quality audio...")
        audio_bytes = await sarvam_service.text_to_speech(
            text=greeting,
            language=request.language
        )
        
        # Store audio and greeting in session
        call_sessions[call_id]["audio_bytes"] = audio_bytes
        call_sessions[call_id]["greeting"] = greeting
        
        # Make REAL Twilio Voice call
        from twilio.rest import Client
        from app.core.config import settings
        
        client = Client(
            settings.TWILIO_ACCOUNT_SID,
            settings.TWILIO_AUTH_TOKEN
        )
        
        # Create TwiML URL for the call
        # This will be the URL Twilio calls to get instructions
        if request.public_url:
            base_url = request.public_url.rstrip('/')
        else:
            base_url = settings.FRONTEND_URL.replace('3000', '8000')
            
        twiml_url = f"{base_url}/api/voice/twiml/{call_id}"
        
        logger.info(f"📞 Making Twilio Voice call to {request.phone_number}")
        logger.info(f"🔗 TwiML URL: {twiml_url}")
        
        # Initiate the call via Twilio
        twilio_call = client.calls.create(
            to=request.phone_number,
            from_=settings.TWILIO_PHONE_NUMBER,
            url=twiml_url,
            method='POST',
            status_callback=f"{settings.FRONTEND_URL.replace('3000', '8000')}/api/voice/status/{call_id}",
            status_callback_event=['initiated', 'ringing', 'answered', 'completed']
        )
        
        # Update session with Twilio call SID
        call_sessions[call_id]["twilio_call_sid"] = twilio_call.sid
        call_sessions[call_id]["twilio_status"] = twilio_call.status
        
        # Audit log
        audit_log(
            event="outbound_call_initiated",
            user_id=request.phone_number,
            metadata={
                "call_id": call_id,
                "twilio_sid": twilio_call.sid,
                "purpose": request.purpose,
                "sector": request.sector,
                "audio_gen": "sarvam_ai"
            }
        )
        
        logger.info(f"✅ REAL Twilio call initiated with Sarvam AI audio!")
        logger.info(f"   Call ID: {call_id}")
        logger.info(f"   Twilio SID: {twilio_call.sid}")
        
        return {
            "success": True,
            "call_id": call_id,
            "twilio_sid": twilio_call.sid,
            "status": twilio_call.status,
            "greeting": greeting,
            "phone_number": request.phone_number,
            "real_call": True,
            "audio_provider": "sarvam_ai"
        }
        
    except Exception as e:
        logger.error(f"❌ Failed to initiate voice call: {str(e)}")
        logger.error(f"   Error type: {type(e).__name__}")
        import traceback
        logger.error(f"   Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Failed to initiate call: {str(e)}")


@router.post("/tts")
async def text_to_speech(
    text: str,
    language: str = "en",
    speaker: str = "meera"
):
    """
    Convert text to speech
    
    Args:
        text: Text to convert
        language: Language code
        speaker: Voice speaker
    
    Returns:
        Audio bytes (base64 encoded)
    """
    try:
        audio_bytes = await sarvam_service.text_to_speech(
            text=text,
            language=language,
            speaker=speaker
        )
        
        import base64
        audio_base64 = base64.b64encode(audio_bytes).decode('utf-8')
        
        return {
            "success": True,
            "audio": audio_base64,
            "language": language,
            "speaker": speaker
        }
        
    except Exception as e:
        logger.error(f"❌ TTS failed: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/stt")
async def speech_to_text(
    audio: UploadFile = File(...),
    language: str = "en"
):
    """
    Convert speech to text
    
    Args:
        audio: Audio file
        language: Expected language
    
    Returns:
        Transcription result
    """
    try:
        # Read audio file
        audio_bytes = await audio.read()
        
        # Transcribe
        result = await sarvam_service.speech_to_text(
            audio_bytes=audio_bytes,
            language=language
        )
        
        return {
            "success": True,
            "transcript": result["transcript"],
            "confidence": result["confidence"],
            "language": result["language"]
        }
        
    except Exception as e:
        logger.error(f"❌ STT failed: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/query")
async def process_voice_query(request: VoiceQueryRequest):
    """
    Process voice query with RAG
    
    Args:
        request: Voice query request
    
    Returns:
        AI response
    """
    try:
        # Get or create session
        session_id = request.session_id or str(uuid.uuid4())
        
        # Generate response (without RAG context)
        response_text = await groq_service.generate_bfsi_response(
            user_query=request.text,
            context="",
            sector=request.sector,
            language=request.language
        )
        
        # Convert to speech
        audio_bytes = await sarvam_service.text_to_speech(
            text=response_text,
            language=request.language
        )
        
        import base64
        audio_base64 = base64.b64encode(audio_bytes).decode('utf-8')
        
        return {
            "success": True,
            "session_id": session_id,
            "text_response": response_text,
            "audio_response": audio_base64,
            "language": request.language
        }
        
    except Exception as e:
        logger.error(f"❌ Voice query failed: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/call/{call_id}")
async def get_call_details(call_id: str):
    """
    Get call session details
    
    Args:
        call_id: Call ID
    
    Returns:
        Call details
    """
    if call_id not in call_sessions:
        raise HTTPException(status_code=404, detail="Call not found")
    
    return {
        "success": True,
        "data": call_sessions[call_id]
    }


@router.post("/call/{call_id}/complete")
async def complete_call(call_id: str, outcome: str):
    """
    Mark call as complete
    
    Args:
        call_id: Call ID
        outcome: Call outcome (completed, no_answer, busy, failed)
    
    Returns:
        Success status
    """
    if call_id not in call_sessions:
        raise HTTPException(status_code=404, detail="Call not found")
    
    call_sessions[call_id]["status"] = "completed"
    call_sessions[call_id]["outcome"] = outcome
    call_sessions[call_id]["completed_at"] = datetime.utcnow().isoformat()
    
    # Audit log
    audit_log(
        event="outbound_call_completed",
        user_id=call_sessions[call_id]["phone_number"],
        metadata={
            "call_id": call_id,
            "outcome": outcome
        }
    )
    
    return {
        "success": True,
        "message": "Call completed"
    }


@router.get("/voices")
async def get_available_voices(language: str = "en"):
    """
    Get available voice speakers
    
    Args:
        language: Language code
    
    Returns:
        List of voices
    """
    try:
        voices = await sarvam_service.get_available_voices(language)
        
        return {
            "success": True,
            "voices": voices
        }
        
    except Exception as e:
        logger.error(f"❌ Failed to get voices: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/twiml/{call_id}")
async def get_twiml_for_call(call_id: str):
    """
    TwiML endpoint for Twilio Voice calls
    Returns instructions to <Play> the Sarvam AI audio
    """
    try:
        from fastapi.responses import Response
        from app.core.config import settings
        
        logger.info(f"📞 TwiML requested for call: {call_id}")
        
        if call_id not in call_sessions:
            logger.error(f"❌ Call session not found: {call_id}")
            twiml = '<?xml version="1.0" encoding="UTF-8"?><Response><Say>Meeting not found.</Say></Response>'
            return Response(content=twiml, media_type="application/xml")
        
        session = call_sessions[call_id]
        
        # Check if audio is likely the mock audio (Sarvam failed)
        # The mock audio header is very small (< 100 bytes usually)
        audio_bytes = session.get("audio_bytes", b"")
        use_fallback_tts = len(audio_bytes) < 100
        
        
        # Language-specific Twilio voices
        TWILIO_VOICES = {
            "en": ("alice", "en-IN"),  # English with Indian accent
            "hi": ("Polly.Aditi", "hi-IN"),  # Hindi (Amazon Polly via Twilio)
            "ta": ("Polly.Aditi", "ta-IN"),  # Tamil
            "te": ("Polly.Aditi", "te-IN"),  # Telugu  
            "mr": ("Polly.Aditi", "mr-IN"),  # Marathi
            "bn": ("Polly.Aditi", "bn-IN"),  # Bengali
        }
        
        # Get language from session
        language = session.get("language", "en")
        voice, lang_code = TWILIO_VOICES.get(language, ("alice", "en-IN"))
        
        if use_fallback_tts:
            logger.warning(f"⚠️ Sarvam TTS failed (size {len(audio_bytes)}), using Twilio TTS with {voice}")
            greeting = session.get("greeting", "Hello, this is a call from your bank.")
            # Escape XML special characters
            greeting = greeting.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
            
            twiml = f'''<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="{voice}" language="{lang_code}">{greeting}</Say>
    <Pause length="1"/>
    <Say voice="{voice}" language="{lang_code}">Thank you for your time. Goodbye.</Say>
</Response>'''
        else:
            # Use public URL for high quality audio
            if session.get("public_url"):
                base_url = session["public_url"].rstrip('/')
            else:
                base_url = settings.FRONTEND_URL.replace('3000', '8000')
                
            audio_url = f"{base_url}/api/voice/audio/{call_id}.wav"
            
            logger.info(f"🔗 Sending TwiML with <Play> URL: {audio_url}")
            
            twiml = f'''<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Play>{audio_url}</Play>
    <Pause length="1"/>
    <Say voice="alice" language="en-IN">Thank you for your time. Goodbye.</Say>
</Response>'''
        
        return Response(content=twiml, media_type="application/xml")
        
    except Exception as e:
        logger.error(f"❌ TwiML generation failed: {str(e)}")
        twiml = '<?xml version="1.0" encoding="UTF-8"?><Response><Say>System error.</Say></Response>'
        return Response(content=twiml, media_type="application/xml")


@router.get("/audio/{call_id}.wav")
async def get_call_audio(call_id: str):
    """Serve the Sarvam AI audio file for a specific call session"""
    from fastapi.responses import Response
    import io
    
    if call_id not in call_sessions or "audio_bytes" not in call_sessions[call_id]:
        logger.error(f"❌ Audio not found for call: {call_id}")
        raise HTTPException(status_code=404, detail="Audio not found")
    
    logger.info(f"🔊 Serving audio bytes for call: {call_id}")
    audio_bytes = call_sessions[call_id]["audio_bytes"]
    
    return Response(
        content=audio_bytes,
        media_type="audio/wav",
        headers={"Content-Length": str(len(audio_bytes))}
    )


@router.post("/status/{call_id}")
async def handle_call_status(
    call_id: str,
    CallSid: str = Form(...),
    CallStatus: str = Form(...),
    From: Optional[str] = Form(None),
    To: Optional[str] = Form(None)
):
    """
    Twilio status callback endpoint
    Receives updates about call status
    
    Args:
        call_id: Call session ID
        CallSid: Twilio call SID
        CallStatus: Current call status
        From: Caller number
        To: Recipient number
    
    Returns:
        Success response
    """
    try:
        logger.info(f"📊 Call status update for {call_id}:")
        logger.info(f"   Twilio SID: {CallSid}")
        logger.info(f"   Status: {CallStatus}")
        logger.info(f"   From: {From}")
        logger.info(f"   To: {To}")
        
        if call_id in call_sessions:
            call_sessions[call_id]["twilio_status"] = CallStatus
            call_sessions[call_id]["last_status_update"] = datetime.utcnow().isoformat()
            
            # Audit log
            audit_log(
                event=f"call_status_{CallStatus}",
                user_id=To or "unknown",
                metadata={
                    "call_id": call_id,
                    "twilio_sid": CallSid,
                    "status": CallStatus
                }
            )
        
        return {"success": True}
        
    except Exception as e:
        logger.error(f"❌ Status callback failed: {str(e)}")
        return {"success": False, "error": str(e)}


# ==================== HELPER FUNCTIONS ====================

async def _generate_call_greeting(request: OutboundCallRequest) -> str:
    """Generate personalized call greeting"""
    
    greetings = {
        "emi_reminder": f"Hello! This is an important automated call from your bank. We are calling to gently remind you that your EMI payment is coming up very soon. To avoid any late fees or charges, please ensure your account is funded. We have also sent you an SMS with the payment details. Thank you for banking with us.",
        "policy_renewal": f"Hello! This is a courtesy call from your insurance provider. We noticed that your insurance policy is due for renewal. Evaluating your coverage options now ensures you stay protected without interruption. Please check your SMS for the renewal link. Thank you for your continued trust in us.",
        "loan_offer": f"Hello! Great news from your bank. Based on your excellent credit history, you have been pre-approved for an exclusive personal loan offer with special interest rates. If you are interested in learning more, please check the SMS we just sent you. This is a limited time offer.",
        "claim_update": f"Hello! This is an update regarding the insurance claim format you recently submitted. We are happy to inform you that your claim is currently being processed by our team. You will receive further updates shortly. Please check your SMS for a link to track the status. Thank you."
    }
    
    greeting = greetings.get(request.purpose, "Hello!")
    
    # Add call recording disclosure
    disclosure = get_call_recording_disclosure(request.language)
    
    full_greeting = f"{greeting} {disclosure}"
    
    return full_greeting
