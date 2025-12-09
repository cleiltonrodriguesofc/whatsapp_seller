/**
 * Status Controller
 * Handles status and QR code endpoints
 */
const qrcode = require('qrcode');

// Referência ao cliente WhatsApp (será injetado pelo app.js)
let whatsappClient;
let qrCodeData;

// Exporta função para injetar o cliente WhatsApp
exports.setWhatsappClient = (client) => {
    whatsappClient = client;
};

// Exporta função para armazenar QR code
exports.setQRCode = (qr) => {
    qrCodeData = qr;
};

/**
 * Get WhatsApp connection status
 */
exports.getStatus = (req, res) => {
    if (!whatsappClient) {
        return res.status(500).json({
            success: false,
            message: 'WhatsApp client not initialized'
        });
    }

    const status = {
        connected: whatsappClient.isReady || false,
        qrAvailable: !!qrCodeData,
        lastActivity: new Date().toISOString()
    };

    return res.json({
        success: true,
        data: status
    });
};

/**
 * Get QR Code for WhatsApp Web connection
 */
exports.getQRCode = async (req, res) => {
    if (!qrCodeData) {
        return res.status(404).json({
            success: false,
            message: 'QR Code not available. Client might be already connected or initializing.'
        });
    }

    try {
        // Gerar QR code como imagem base64
        const qrImage = await qrcode.toDataURL(qrCodeData);
        
        return res.json({
            success: true,
            data: {
                qrCode: qrImage,
                expiresAt: new Date(Date.now() + 5 * 60 * 1000).toISOString() // 5 minutos
            }
        });
    } catch (error) {
        console.error('Error generating QR code:', error);
        return res.status(500).json({
            success: false,
            message: 'Failed to generate QR code'
        });
    }
};

