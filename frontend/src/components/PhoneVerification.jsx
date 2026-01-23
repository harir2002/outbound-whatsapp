import { useState, useEffect } from 'react'
import { verificationAPI } from '../api'
import './PhoneVerification.css'

function PhoneVerification({ onVerified, initialPhoneNumber = '' }) {
    const [step, setStep] = useState('enter-number') // 'enter-number', 'verify-code', 'verified'
    const [phoneNumber, setPhoneNumber] = useState(initialPhoneNumber)
    const [code, setCode] = useState('')
    const [loading, setLoading] = useState(false)
    const [message, setMessage] = useState('')
    const [debugCode, setDebugCode] = useState('')

    // Initialize with provided phone number if available
    useEffect(() => {
        if (initialPhoneNumber) {
            setPhoneNumber(initialPhoneNumber)
        }
    }, [initialPhoneNumber])

    const sendVerificationCode = async () => {
        if (!phoneNumber) {
            setMessage('Please enter a phone number')
            return
        }

        if (!phoneNumber.startsWith('+')) {
            setMessage('Phone number must start with + and country code (e.g., +919876543210)')
            return
        }

        try {
            setLoading(true)
            setMessage('')
            const response = await verificationAPI.sendCode(phoneNumber)

            setMessage('✅ Verification code sent to your phone!')
            setStep('verify-code')

            // Show debug code in development
            if (response.data.debug_code) {
                setDebugCode(response.data.debug_code)
            }
        } catch (error) {
            setMessage('❌ Failed to send code: ' + (error.response?.data?.detail || error.message))
        } finally {
            setLoading(false)
        }
    }

    const verifyCode = async () => {
        if (!code || code.length !== 6) {
            setMessage('Please enter the 6-digit code')
            return
        }

        try {
            setLoading(true)
            setMessage('')
            const response = await verificationAPI.verifyCode(phoneNumber, code)

            setMessage('✅ Phone number verified successfully!')
            setStep('verified')

            // Notify parent component
            if (onVerified) {
                onVerified(phoneNumber)
            }
        } catch (error) {
            setMessage('❌ ' + (error.response?.data?.detail || 'Verification failed'))
        } finally {
            setLoading(false)
        }
    }

    const resetVerification = () => {
        setStep('enter-number')
        setPhoneNumber('')
        setCode('')
        setMessage('')
        setDebugCode('')
    }

    return (
        <div className="phone-verification">
            <div className="verification-header">
                <h3>📱 Verify Your Phone Number</h3>
                <p className="text-muted">
                    {step === 'enter-number' && 'Enter your phone number to receive a verification code'}
                    {step === 'verify-code' && 'Enter the 6-digit code sent to your phone'}
                    {step === 'verified' && 'Your phone number is verified!'}
                </p>
            </div>

            {step === 'enter-number' && (
                <div className="verification-step">
                    <div className="form-group">
                        <label className="form-label">Phone Number</label>
                        <input
                            type="tel"
                            className="form-input"
                            placeholder="+919876543210"
                            value={phoneNumber}
                            onChange={(e) => setPhoneNumber(e.target.value)}
                            disabled={loading}
                        />
                        <small className="text-muted">
                            Include country code (e.g., +91 for India)
                        </small>
                    </div>

                    <button
                        className="btn btn-primary"
                        onClick={sendVerificationCode}
                        disabled={loading}
                    >
                        {loading ? '📤 Sending...' : '📤 Send Verification Code'}
                    </button>
                </div>
            )}

            {step === 'verify-code' && (
                <div className="verification-step">
                    <div className="phone-display">
                        <strong>Phone:</strong> {phoneNumber}
                        <button className="btn-link" onClick={resetVerification}>Change</button>
                    </div>

                    <div className="form-group">
                        <label className="form-label">Verification Code</label>
                        <input
                            type="text"
                            className="form-input code-input"
                            placeholder="000000"
                            maxLength="6"
                            value={code}
                            onChange={(e) => setCode(e.target.value.replace(/\D/g, ''))}
                            disabled={loading}
                            autoFocus
                        />

                    </div>

                    <div className="button-group">
                        <button
                            className="btn btn-primary"
                            onClick={verifyCode}
                            disabled={loading || code.length !== 6}
                        >
                            {loading ? '⏳ Verifying...' : '✅ Verify Code'}
                        </button>
                        <button
                            className="btn btn-secondary"
                            onClick={sendVerificationCode}
                            disabled={loading}
                        >
                            🔄 Resend Code
                        </button>
                    </div>

                    <small className="text-muted">
                        Code expires in 5 minutes
                    </small>
                </div>
            )}

            {step === 'verified' && (
                <div className="verification-step verified">
                    <div className="success-icon">✅</div>
                    <h4>Verification Successful!</h4>
                    <p>
                        <strong>{phoneNumber}</strong> is now verified and ready to receive calls.
                    </p>
                    <button
                        className="btn btn-secondary"
                        onClick={resetVerification}
                    >
                        Verify Another Number
                    </button>
                </div>
            )}

            {message && (
                <div className={`message ${message.includes('✅') ? 'success' : message.includes('❌') ? 'error' : 'info'}`}>
                    {message}
                </div>
            )}

            <div className="verification-info">
                <h4>ℹ️ Why Verify?</h4>
                <ul>
                    <li>✅ Confirms ownership of the number</li>
                    <li>✅ Ensures calls reach your number</li>
                    <li>✅ One-time verification per number</li>
                    <li>✅ Free SMS verification code</li>
                </ul>
            </div>
        </div>
    )
}

export default PhoneVerification
