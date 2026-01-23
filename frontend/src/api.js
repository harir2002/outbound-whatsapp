import axios from 'axios'

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8001'

const api = axios.create({
    baseURL: API_BASE_URL,
    headers: {
        'Content-Type': 'application/json'
    }
})

// WhatsApp API
export const whatsappAPI = {
    sendMessage: (data) => api.post('/api/whatsapp/send', data),
    sendPaymentLink: (data) => api.post('/api/whatsapp/send-payment-link', data),
    sendPolicyDetails: (data) => api.post('/api/whatsapp/send-policy-details', data),
    sendLoanSummary: (data) => api.post('/api/whatsapp/send-loan-summary', data),
    recordOptIn: (phoneNumber) => api.post('/api/whatsapp/opt-in', { phone_number: phoneNumber }),
    recordOptOut: (phoneNumber) => api.post('/api/whatsapp/opt-out', { phone_number: phoneNumber })
}

// SMS API
export const smsAPI = {
    sendMessage: (data) => api.post('/api/sms/send', data)
}

// Voice API
export const voiceAPI = {
    initiateCall: (data) => api.post('/api/voice/outbound', data),
    textToSpeech: (data) => api.post('/api/voice/tts', data),
    speechToText: (formData) => api.post('/api/voice/stt', formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
    }),
    processQuery: (data) => api.post('/api/voice/query', data),
    getCallDetails: (callId) => api.get(`/api/voice/call/${callId}`),
    completeCall: (callId, outcome) => api.post(`/api/voice/call/${callId}/complete`, { outcome }),
    getVoices: (language) => api.get('/api/voice/voices', { params: { language } })
}





// Analytics API
export const analyticsAPI = {
    getOverview: () => api.get('/api/analytics/overview'),
    getCalls: (filter) => api.post('/api/analytics/calls', filter),
    getMessages: (filter) => api.post('/api/analytics/messages', filter),
    getIntents: () => api.get('/api/analytics/intents'),
    recordCall: (data) => api.post('/api/analytics/record-call', data),
    recordMessage: (data) => api.post('/api/analytics/record-message', data),
    recordIntent: (data) => api.post('/api/analytics/record-intent', data)
}

// Verification API
export const verificationAPI = {
    sendCode: (phoneNumber) => api.post('/api/verification/send-code', { phone_number: phoneNumber }),
    verifyCode: (phoneNumber, code) => api.post('/api/verification/verify-code', { phone_number: phoneNumber, code }),
    checkStatus: (phoneNumber) => api.get(`/api/verification/check/${phoneNumber}`),
    getVerifiedNumbers: () => api.get('/api/verification/verified-numbers'),
    resetVerification: (phoneNumber) => api.delete(`/api/verification/reset/${phoneNumber}`)
}

// Health check
export const healthCheck = () => api.get('/health')

export default api
