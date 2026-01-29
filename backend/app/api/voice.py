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
from app.services.twilio_service import twilio_whatsapp_service
from app.services.email_service import email_service
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
        
        # Send Email Notification
        email_address = request.customer_data.get("email")
        if email_address:
            email_content = _generate_notification_content(request.purpose)
            logger.info(f"📧 Sending Email to {email_address}")
            try:
                await email_service.send_email(
                    to_email=email_address,
                    subject="Important Notification from Your Bank", 
                    body=email_content
                )
            except Exception as email_error:
                logger.error(f"⚠️ Failed to send email: {str(email_error)}")
        else:
            logger.warning(f"⚠️ No email address provided for {request.phone_number}, skipping email notification")

        # Get language config for appropriate speaker
        lang_config = sarvam_service.get_language_config(request.language)
        speaker = lang_config.get("speaker", "meera")
        
        # Convert to speech using SARVAM AI (High Quality)
        logger.info(f"🎙️ Generating Sarvam AI high-quality audio with speaker {speaker}...")
        audio_bytes = await sarvam_service.text_to_speech(
            text=greeting,
            language=request.language,
            speaker=speaker
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
        elif settings.PUBLIC_URL:
            base_url = settings.PUBLIC_URL.rstrip('/')
        else:
            base_url = settings.FRONTEND_URL.replace('3000', '8000')
            
        twiml_url = f"{base_url}/api/voice/twiml/{call_id}"
        
        logger.info(f"📞 Making Twilio Voice call to {request.phone_number}")
        logger.info(f"🔗 TwiML URL: {twiml_url}")
        
        # Initiate the call via Twilio
        # Use PUBLIC_URL for status callback if available
        status_callback_url = f"{base_url}/api/voice/status/{call_id}"
        
        twilio_call = client.calls.create(
            to=request.phone_number,
            from_=settings.TWILIO_PHONE_NUMBER,
            url=twiml_url,
            method='POST',
            status_callback=status_callback_url,
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
            elif settings.PUBLIC_URL:
                base_url = settings.PUBLIC_URL.rstrip('/')
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

def _generate_notification_content(purpose: str) -> str:
    """Generate Notification content with SBA Info link"""
    
    # Unified link for all notifications
    link = "https://bfsi-voice-agent.vercel.app"
    
    templates = {
        "emi_reminder": f"Alert: Your EMI payment is approaching. Amount due: Rs. 15,000. Pay by 5th to avoid late fees. Pay here: {link}",
        "policy_renewal": f"Reminder: Your insurance policy renews on 30 Jan. Premium: Rs. 12000. Renew now to stay protected: {link}",
        "loan_offer": f"Congratulations! You are pre-approved for a personal loan up to Rs. 5 Lakhs @ 10.99% p.a. Apply now: {link}",
        "claim_update": f"Update: Your claim #CLM987654 is now under process. We will notify you once approved. Track status: {link}",
        "debt_recovery": f"CreditMantri Alert: 40% Waiver on your outstanding dues available for TODAY only. Clear your debt now: {link}",
        "lead_generation": f"CreditMantri Offer: You are pre-approved for a ₹5L Personal Loan. No paperwork. Claim now: {link}",
        "credit_repair": f"Credit Alert: Your score has dropped. Fix errors and improve your score with CreditFit. Check report: {link}",
        "default": f"Alert: You have a new notification from your bank. {link}"
    }
    
    return templates.get(purpose, templates["default"])

async def _generate_call_greeting(request: OutboundCallRequest) -> str:
    """Generate personalized call greeting"""
    
    # English Greetings
    greetings_en = {
        "emi_reminder": f"Hello! This is an important automated call from your bank. We are calling to gently remind you that your EMI payment is coming up very soon. To avoid any late fees or charges, please ensure your account is funded. We have also sent you an email with the payment details. Thank you for banking with us.",
        "policy_renewal": f"Hello! This is a courtesy call from your insurance provider. We noticed that your insurance policy is due for renewal. Evaluating your coverage options now ensures you stay protected without interruption. Please check your email for the renewal link. Thank you for your continued trust in us.",
        "loan_offer": f"Hello! Great news from your bank. Based on your excellent credit history, you have been pre-approved for an exclusive personal loan offer with special interest rates. If you are interested in learning more, please check the email we just sent you. This is a limited time offer.",
        "claim_update": f"Hello! This is an update regarding the insurance claim format you recently submitted. We are happy to inform you that your claim is currently being processed by our team. You will receive further updates shortly. Please check your email for a link to track the status. Thank you.",
        "debt_recovery": "Hello, this is a priority message from CreditMantri. We have partnered with your bank to offer a 40% waiver on your outstanding dues for today only. Clear your debt and start improving your credit score now. Check the link sent to your email to view your offer.",
        "lead_generation": "Great news! Based on your CreditMantri profile, you are now pre-approved for a Personal Loan of up to 5 Lakh rupees at a special interest rate. No paperwork required. Visit the CreditMantri app or click the email link to claim your funds instantly.",
        "credit_repair": "Hi, your credit score has recently dropped. This could prevent you from getting future loans. CreditMantri’s CreditFit experts are here to help you fix errors and remove negative entries. Check your personalized Credit Health Report via the link sent to your email.",
        "default": "Hello! This is a call from your bank."
    }

    # Hindi Greetings
    greetings_hi = {
        "emi_reminder": "नमस्ते! यह आपके बैंक से एक महत्वपूर्ण कॉल है। हम आपको याद दिलाने के लिए कॉल कर रहे हैं कि आपका ईएमआई भुगतान जल्द ही आने वाला है। किसी भी विलंब शुल्क से बचने के लिए, कृपया सुनिश्चित करें कि आपके खाते में पर्याप्त राशि है। हमने आपको भुगतान विवरण के साथ एक ईमेल भी भेजा है। हमारे साथ बने रहने के लिए धन्यवाद।",
        "policy_renewal": "नमस्ते! यह आपके बीमा प्रदाता की ओर से एक कॉल है। हमने देखा कि आपकी बीमा पॉलिसी का नवीनीकरण होने वाला है। अपनी कवरेज का मूल्यांकन अभी करें ताकि आप बिना किसी रुकावट के सुरक्षित रहें। कृपया नवीनीकरण लिंक के लिए अपना ईमेल देखें। हम पर भरोसा करने के लिए धन्यवाद।",
        "loan_offer": "नमस्ते! आपके बैंक से अच्छी खबर है। आपके उत्कृष्ट क्रेडिट इतिहास के आधार पर, आपको विशेष ब्याज दरों के साथ एक व्यक्तिगत ऋण प्रस्ताव के लिए पूर्व-अनुमोदित किया गया है। यदि आप अधिक जानने में रुचि रखते हैं, तो कृपया हमारे द्वारा अभी भेजे गए ईमेल को देखें। यह एक सीमित समय की पेशकश है।",
        "claim_update": "नमस्ते! यह आपके द्वारा हाल ही में जमा किए गए बीमा दावे के प्रारूप के बारे में एक अपडेट है। हमें आपको यह बताते हुए खुशी हो रही है कि हमारी टीम वर्तमान में आपके दावे पर कार्रवाई कर रही है। आपको जल्द ही और अपडेट प्राप्त होंगे। स्थिति को ट्रैक करने के लिए लिंक के लिए कृपया अपना ईमेल देखें। धन्यवाद।",
        "debt_recovery": "नमस्ते, यह CreditMantri से आपके लिए एक ज़रूरी संदेश है। हमने आपके बैंक के साथ मिलकर आपके पुराने क़र्ज़े पर 40% तक की छूट का ऑफर निकाला है। आज ही अपना सेटलमेंट करें और अपना क्रेडिट स्कोर सुधारें। ईमेल में दिए गए लिंक पर क्लिक करें।",
        "lead_generation": "बधाई हो! आपके CreditMantri प्रोफाइल के हिसाब से, आप 5 लाख तक के पर्सनल लोन के लिए प्री-अप्रूव्ड हैं। इसका इंटरेस्ट रेट बहुत कम है और कोई पेपरवर्क नहीं लगेगा। ईमेल में दिए गए लिंक पर क्लिक करें और पैसे तुरंत अपने अकाउंट में पाएं।",
        "credit_repair": "नमस्ते, आपका क्रेडिट स्कोर हाल ही में गिर गया है। इस वजह से आपको आगे लोन मिलने में दिक़्क़त हो सकती है। CreditMantri के एक्सपर्ट्स आपकी रिपोर्ट से गलतियां हटाने में मदद कर सकते हैं। अपने ईमेल पर भेजे गए लिंक से अपनी क्रेडिट हेल्थ रिपोर्ट चेक करें।",
        "default": "नमस्ते! यह आपके बैंक से एक कॉल है।"
    }

    # Tamil Greetings
    greetings_ta = {
        "emi_reminder": "வணக்கம்! இது உங்கள் வங்கியிலிருந்து வரும் முக்கியமான அழைப்பு. உங்கள் இஎம்ஐ கட்டணம் விரைவில் வரவுள்ளது என்பதை நினைவுபடுத்துகிறோம். தாமதக் கட்டணங்களைத் தவிர்க்க, உங்கள் கணக்கில் பணம் இருப்பதை உறுதிசெய்யவும். கட்டண விவரங்களுடன் ஒரு மின்னஞ்சலையும் (email) அனுப்பியுள்ளோம். எங்களுடன் இணைந்திருப்பதற்கு நன்றி.",
        "policy_renewal": "வணக்கம்! இது உங்கள் காப்பீட்டு வழங்குநரிடமிருந்து ஒரு அழைப்பு. உங்கள் காப்பீட்டுக் கொள்கை புதுப்பிக்கப்பட உள்ளதை கவனித்தோம். தடையின்றி பாதுகாப்பாக இருக்க உங்கள் காப்பீட்டுத் திட்டத்தை இப்போதே மதிப்பாய்வு செய்யுங்கள். புதுப்பிப்பு இணைப்பிற்கு உங்கள் மின்னஞ்சலை (email) பார்க்கவும். எங்கள் மீதான உங்கள் நம்பிக்கைக்கும் நன்றி.",
        "loan_offer": "வணக்கம்! உங்கள் வங்கியிலிருந்து ஒரு நற்செய்தி. உங்கள் சிறந்த கிரெடிட் வரலாற்றின் அடிப்படையில், சிறப்பு வட்டி விகிதங்களுடன் தனிநபர் கடன் வழங்க உங்களுக்கு முன்னனுமதி அளிக்கப்பட்டுள்ளது. மேலும் விவரங்களுக்கு, நாங்கள் அனுப்பிய மின்னஞ்சலை (email) பார்க்கவும். இது குறைந்த கால சலுகை.",
        "claim_update": "வணக்கம்! இது நீங்கள் சமீபத்தில் சமர்ப்பித்த காப்பீட்டு கோரிக்கை தொடர்பான தகவல். உங்கள் கோரிக்கை தற்போது எங்கள் குழுவால் செயலாக்கப்பட்டு வருகிறது என்பதை மகிழ்ச்சியுடன் தெரிவித்துக்கொள்கிறோம். விரைவில் கூடுதல் தகவல்களைப் பெறுவீர்கள். நிலையை அறிய உங்கள் மின்னஞ்சலில் (email) உள்ள இணைப்பைச் சரிபார்க்கவும். நன்றி.",
        "debt_recovery": "வணக்கம், CreditMantri-yidhirundhu oru mukkiya arivippu. Ungal bank-udhan inaindhu, ungal kadan thogaiyil 40% thallupadi vazhangugirrom. Indha vaaippai payanpaduththi ungal credit score-ai uyarththungal. Melum vivaranangalukku ungal email-il ulla link-ai paarungal.",
        "lead_generation": "Nalla seidhi! Ungal CreditMantri profile-in padi, 5 latcham rupai varaiyilana Personal Loan ungalukku pre-approved seiyappattulladhu. Paperwork edhum indri kuraivaana vatti vidhaththil indha loan-ai pera email-il ulla link-ai click seiyungal.",
        "credit_repair": "வணக்கம், ungal credit score tharpoathu kuraivaga ulladhu. Idhanaal ungalukku loan kidaikkaadhau poga vaaippu ulladhu. CreditMantri-yin vallunargal ungal report-il ulla thavarugalai thiruththi score-ai uyarththa udhavuvaargal. Email-il ulla link-ai paarththu payan perungal.",
        "default": "வணக்கம்! இது உங்கள் வங்கியிலிருந்து ஒரு அழைப்பு."
    }

    # Map languages to greetings
    all_greetings = {
        "en": greetings_en,
        "hi": greetings_hi,
        "ta": greetings_ta
    }

    # Get localized greetings based on request language, default to English
    selected_greetings = all_greetings.get(request.language, greetings_en)
    
    # Get specific purpose greeting or default
    greeting = selected_greetings.get(request.purpose, selected_greetings["default"])
    
    # Add call recording disclosure
    disclosure = get_call_recording_disclosure(request.language)
    
    full_greeting = f"{greeting} {disclosure}"
    
    return full_greeting
