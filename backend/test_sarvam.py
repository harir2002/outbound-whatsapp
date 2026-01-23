"""
Test Sarvam TTS API directly to diagnose the issue
"""
import httpx
import asyncio
import base64
import os
from dotenv import load_dotenv

load_dotenv()

async def test_sarvam_tts():
    api_key = os.getenv("SARVAM_API_KEY")
    api_url = os.getenv("SARVAM_API_URL", "https://api.sarvam.ai/v1")
    
    print(f"API Key: {api_key[:10]}... (length: {len(api_key)})")
    print(f"API URL: {api_url}")
    print()
    
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "text": "Hello, this is a test message from the BFSI AI platform.",
        "language_code": "en",
        "speaker": "meera",
        "speed": 1.0,
        "model": "bulbul:v1"
    }
    
    print("Sending request to Sarvam API...")
    print(f"Payload: {payload}")
    print()
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{api_url}/text-to-speech",
                headers=headers,
                json=payload,
                timeout=30.0
            )
            
            print(f"Response Status: {response.status_code}")
            print(f"Response Headers: {dict(response.headers)}")
            print()
            
            if response.status_code == 200:
                result = response.json()
                print(f"SUCCESS!")
                print(f"Keys in response: {list(result.keys())}")
                
                if "audio" in result:
                    audio_base64 = result.get("audio", "")
                    audio_bytes = base64.b64decode(audio_base64)
                    print(f"Audio size: {len(audio_bytes)} bytes")
                    print(f"Audio base64 preview: {audio_base64[:50]}...")
                else:
                    print(f"WARNING: No 'audio' key in response!")
                    print(f"Full response: {result}")
            else:
                print(f"ERROR!")
                print(f"Response body: {response.text}")
                
    except httpx.HTTPStatusError as e:
        print(f"HTTP Error: {e.response.status_code}")
        print(f"Response: {e.response.text}")
    except Exception as e:
        print(f"Exception: {type(e).__name__}: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_sarvam_tts())
