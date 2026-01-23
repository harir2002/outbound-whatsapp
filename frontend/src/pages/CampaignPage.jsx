import { useState } from 'react'
import { voiceAPI, whatsappAPI, smsAPI } from '../api'
import PhoneVerification from '../components/PhoneVerification'
import './CampaignPage.css'

function CampaignPage() {
    const [formData, setFormData] = useState({
        phoneNumber: '',
        customerName: '',
        campaignType: 'emi_reminder',
        sector: 'banking',
        language: 'en',
        amount: '',
        dueDate: '',
        messageType: 'sms', // Default to SMS as it's easier to test
        ngrokUrl: import.meta.env.VITE_API_URL || ''
    })

    const [loading, setLoading] = useState(false)
    const [status, setStatus] = useState('')
    const [callId, setCallId] = useState('')
    const [showVerification, setShowVerification] = useState(false)

    const handleVerified = (verifiedNumber) => {
        setFormData({ ...formData, phoneNumber: verifiedNumber })
        setShowVerification(false)
        setStatus(`✅ Number ${verifiedNumber} verified! You can now make calls.`)
    }

    const handleChange = (e) => {
        setFormData({
            ...formData,
            [e.target.name]: e.target.value
        })
    }

    const startCampaign = async () => {
        if (!formData.phoneNumber) {
            alert('Please enter phone number')
            return
        }

        const publicUrl = import.meta.env.VITE_API_URL || 'http://localhost:8001'

        try {
            setLoading(true)
            setStatus('📞 Initiating voice call...')

            // Step 1: Make outbound voice call
            const voiceResponse = await voiceAPI.initiateCall({
                phone_number: formData.phoneNumber,
                purpose: formData.campaignType,
                sector: formData.sector,
                language: formData.language,
                customer_data: {
                    name: formData.customerName,
                    amount: formData.amount,
                    due_date: formData.dueDate
                },
                public_url: publicUrl
            })

            const newCallId = voiceResponse.data.call_id
            setCallId(newCallId)
            setStatus('✅ Voice call initiated! Call ID: ' + newCallId)

            // Wait for call to complete (simulate - in production, use webhook)
            await new Promise(resolve => setTimeout(resolve, 3000))

            if (formData.messageType === 'whatsapp') {
                setStatus('📱 Sending WhatsApp follow-up...')
                const whatsappMessage = generateFollowUpMessage(formData)
                await whatsappAPI.sendMessage({
                    to_number: formData.phoneNumber,
                    message: whatsappMessage
                })
                setStatus('✅ Campaign completed! Voice call made + WhatsApp sent')
            } else {
                setStatus('💬 Sending SMS follow-up...')
                const smsMessage = generateFollowUpMessage(formData)
                await smsAPI.sendMessage({
                    to_number: formData.phoneNumber,
                    message: smsMessage
                })
                setStatus('✅ Campaign completed! Voice call made + SMS sent')
            }

        } catch (error) {
            console.error('Campaign error:', error)

            // Extract detailed error message
            let errorMessage = 'Unknown error'
            if (error.response) {
                // Server responded with error
                const data = error.response.data
                if (typeof data === 'string') {
                    errorMessage = data
                } else if (data?.detail) {
                    errorMessage = typeof data.detail === 'string' ? data.detail : JSON.stringify(data.detail)
                } else if (data?.message) {
                    errorMessage = data.message
                } else {
                    errorMessage = `Server error: ${error.response.status} - ${JSON.stringify(data)}`
                }
                console.error('Server error details:', error.response.data)
            } else if (error.request) {
                // Request made but no response
                errorMessage = 'No response from server. Is the backend running?'
            } else {
                // Error in request setup
                errorMessage = error.message || 'Request failed'
            }

            setStatus(`❌ Error: ${errorMessage}`)
        } finally {
            setLoading(false)
        }
    }

    const generateFollowUpMessage = (data) => {
        const messages = {
            emi_reminder: `
Hi ${data.customerName || 'Customer'},

This is a reminder about your upcoming EMI payment.

💰 Amount: ₹${data.amount || 'N/A'}
📅 Due Date: ${data.dueDate || 'N/A'}

We tried calling you. Please make the payment to avoid late fees.

Reply PAY to get payment link.
Reply HELP for assistance.

Thank you!
      `.trim(),

            policy_renewal: `
Hi ${data.customerName || 'Customer'},

Your insurance policy is due for renewal.

💰 Premium: ₹${data.amount || 'N/A'}
📅 Renewal Date: ${data.dueDate || 'N/A'}

We tried calling you. Renew now to continue your coverage.

Reply RENEW to get renewal link.
Reply HELP for assistance.

Thank you!
      `.trim(),

            loan_offer: `
Hi ${data.customerName || 'Customer'},

We have an exclusive loan offer for you!

💰 Loan Amount: Up to ₹${data.amount || '5,00,000'}
✨ Special Rate: Starting from 10.5% p.a.

We tried calling you. This is a limited time offer.

Reply APPLY to get application link.
Reply HELP for more details.

Thank you!
      `.trim(),

            claim_update: `
Hi ${data.customerName || 'Customer'},

Update on your insurance claim.

📋 Claim Amount: ₹${data.amount || 'N/A'}
📅 Expected Date: ${data.dueDate || 'Processing'}

We tried calling you. Your claim is being processed.

Reply STATUS for latest update.
Reply HELP for assistance.

Thank you!
      `.trim()
        }

        return messages[data.campaignType] || messages.emi_reminder
    }

    return (
        <div className="campaign-page container">
            <div className="page-header">
                <h1>📞 Outbound Campaign</h1>
                <p className="text-muted">
                    Make voice call + Send WhatsApp follow-up automatically
                </p>
            </div>

            <div className="campaign-grid">
                {/* Campaign Form */}
                <div className="card campaign-form">


                    <div className="form-group">


                        <label className="form-label">Campaign Type</label>
                        <select
                            className="form-select"
                            name="campaignType"
                            value={formData.campaignType}
                            onChange={handleChange}
                        >
                            <option value="emi_reminder">EMI Reminder</option>
                            <option value="policy_renewal">Policy Renewal</option>
                            <option value="loan_offer">Loan Offer</option>
                            <option value="claim_update">Claim Status Update</option>
                        </select>
                    </div>

                    <div className="form-group">
                        <label className="form-label">Sector</label>
                        <select
                            className="form-select"
                            name="sector"
                            value={formData.sector}
                            onChange={handleChange}
                        >
                            <option value="banking">Banking</option>
                            <option value="insurance">Insurance</option>
                            <option value="nbfc">NBFC</option>
                            <option value="mutual_funds">Mutual Funds</option>
                        </select>
                    </div>

                    <div className="form-group">
                        <label className="form-label">Language</label>
                        <select
                            className="form-select"
                            name="language"
                            value={formData.language}
                            onChange={handleChange}
                        >
                            <option value="en">English</option>
                            <option value="hi">Hindi</option>
                            <option value="ta">Tamil</option>
                            <option value="te">Telugu</option>
                            <option value="mr">Marathi</option>
                            <option value="bn">Bengali</option>
                        </select>
                    </div>

                    <div className="form-group">
                        <label className="form-label">Follow-up Channel</label>
                        <div className="channel-selector">
                            <label className="radio-label">
                                <input
                                    type="radio"
                                    name="messageType"
                                    value="sms"
                                    checked={formData.messageType === 'sms'}
                                    onChange={handleChange}
                                />
                                Direct SMS (Recommended)
                            </label>
                            <label className="radio-label" style={{ marginLeft: '20px' }}>
                                <input
                                    type="radio"
                                    name="messageType"
                                    value="whatsapp"
                                    checked={formData.messageType === 'whatsapp'}
                                    onChange={handleChange}
                                />
                                WhatsApp (Requires Sandbox)
                            </label>
                        </div>
                    </div>

                    <div className="form-group">
                        <label className="form-label">Customer Name</label>
                        <input
                            type="text"
                            className="form-input"
                            name="customerName"
                            placeholder="Rajesh Kumar"
                            value={formData.customerName}
                            onChange={handleChange}
                        />
                    </div>

                    <div className="form-group">
                        <label className="form-label">Phone Number (with country code)</label>
                        <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'flex-start' }}>
                            <input
                                type="text"
                                className="form-input"
                                name="phoneNumber"
                                placeholder="+919876543210"
                                value={formData.phoneNumber}
                                onChange={handleChange}
                                style={{ flex: 1 }}
                            />
                            <button
                                type="button"
                                className="btn btn-secondary"
                                onClick={() => setShowVerification(true)}
                                style={{ whiteSpace: 'nowrap' }}
                            >
                                🔐 Verify Number
                            </button>
                        </div>
                        <small className="text-muted">
                            ℹ️ Optional: Verify your number to ensure SMS delivery.
                        </small>
                    </div>

                    <div className="form-group">
                        <label className="form-label">Amount (₹)</label>
                        <input
                            type="text"
                            className="form-input"
                            name="amount"
                            placeholder="25000"
                            value={formData.amount}
                            onChange={handleChange}
                        />
                    </div>

                    <div className="form-group">
                        <label className="form-label">Due Date / Renewal Date</label>
                        <input
                            type="date"
                            className="form-input"
                            name="dueDate"
                            value={formData.dueDate}
                            onChange={handleChange}
                        />
                    </div>

                    <button
                        className="btn btn-primary btn-large"
                        onClick={startCampaign}
                        disabled={loading}
                    >
                        {loading ? '⏳ Processing...' : '🚀 Start Campaign'}
                    </button>

                    {status && (
                        <div className={`status-message ${status.includes('✅') ? 'success' : status.includes('❌') ? 'error' : 'info'}`}>
                            {status}
                        </div>
                    )}

                    {callId && (
                        <div className="call-id-display">
                            <strong>Call ID:</strong> {callId}
                        </div>
                    )}
                </div>

                {/* Campaign Flow */}
                <div className="card campaign-flow">
                    <h3>Campaign Flow</h3>

                    <div className="flow-steps">
                        <div className="flow-step">
                            <div className="step-number">1</div>
                            <div className="step-content">
                                <h4>📞 Voice Call</h4>
                                <p>AI makes outbound call in selected language</p>
                                <ul>
                                    <li>Personalized greeting</li>
                                    <li>Reminder/offer details</li>
                                    <li>Capture customer response</li>
                                    <li>Call recording (with consent)</li>
                                </ul>
                            </div>
                        </div>

                        <div className="flow-arrow">↓</div>

                        <div className="flow-step">
                            <div className="step-number">2</div>
                            <div className="step-content">
                                <h4>💬 WhatsApp Follow-up</h4>
                                <p>Automatic message sent after call</p>
                                <ul>
                                    <li>Summary of call</li>
                                    <li>Payment/action links</li>
                                    <li>Contact information</li>
                                    <li>Next steps</li>
                                </ul>
                            </div>
                        </div>

                        <div className="flow-arrow">↓</div>

                        <div className="flow-step">
                            <div className="step-number">3</div>
                            <div className="step-content">
                                <h4>📊 Track Results</h4>
                                <p>Monitor campaign performance</p>
                                <ul>
                                    <li>Call status</li>
                                    <li>Customer response</li>
                                    <li>WhatsApp delivery</li>
                                    <li>Analytics</li>
                                </ul>
                            </div>
                        </div>
                    </div>

                    <div className="campaign-benefits">
                        <h4>✨ Benefits</h4>
                        <ul>
                            <li>✅ Automated workflow</li>
                            <li>✅ Multi-channel engagement</li>
                            <li>✅ Multilingual support</li>
                            <li>✅ Higher conversion rates</li>
                            <li>✅ Reduced manual effort</li>
                        </ul>
                    </div>
                </div>
            </div>

            {/* Quick Examples */}
            <div className="card examples-section">
                <h3>📋 Quick Examples</h3>
                <div className="examples-grid">
                    <div className="example-card">
                        <h5>EMI Reminder</h5>
                        <p>Voice: "Your EMI of ₹25,000 is due on 5th Feb"</p>
                        <p>WhatsApp: Payment link + details</p>
                    </div>
                    <div className="example-card">
                        <h5>Policy Renewal</h5>
                        <p>Voice: "Your policy expires on 15th March"</p>
                        <p>WhatsApp: Renewal link + coverage details</p>
                    </div>
                    <div className="example-card">
                        <h5>Loan Offer</h5>
                        <p>Voice: "Pre-approved loan up to ₹5 lakhs"</p>
                        <p>WhatsApp: Application link + terms</p>
                    </div>
                    <div className="example-card">
                        <h5>Claim Update</h5>
                        <p>Voice: "Your claim is being processed"</p>
                        <p>WhatsApp: Status + documents needed</p>
                    </div>
                </div>
            </div>

            {/* Verification Modal */}
            {showVerification && (
                <div className="modal-overlay" onClick={() => setShowVerification(false)}>
                    <div className="modal-content" onClick={(e) => e.stopPropagation()}>
                        <button
                            className="modal-close"
                            onClick={() => setShowVerification(false)}
                            aria-label="Close"
                        >
                            ✕
                        </button>
                        <PhoneVerification
                            onVerified={handleVerified}
                            initialPhoneNumber={formData.phoneNumber}
                        />
                    </div>
                </div>
            )}
        </div>
    )
}

export default CampaignPage
