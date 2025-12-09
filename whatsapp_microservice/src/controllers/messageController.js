/**
 * Message Controller
 * Handles sending messages, images and files
 */

// Referência ao cliente WhatsApp (será injetado pelo app.js)
let whatsappClient;

// Exporta função para injetar o cliente WhatsApp
exports.setWhatsappClient = (client) => {
    whatsappClient = client;
};

/**
 * Send a text message to a WhatsApp number
 */
exports.sendMessage = async (req, res) => {
    if (!whatsappClient || !whatsappClient.isReady) {
        return res.status(400).json({
            success: false,
            message: 'WhatsApp client not connected'
        });
    }

    const { phone, message } = req.body;

    try {
        // Formatar número para padrão internacional
        const formattedPhone = formatPhoneNumber(phone);
        
        // Enviar mensagem
        const response = await whatsappClient.sendMessage(`${formattedPhone}@c.us`, message);
        
        return res.json({
            success: true,
            data: {
                messageId: response.id._serialized,
                timestamp: new Date().toISOString()
            }
        });
    } catch (error) {
        console.error('Error sending message:', error);
        return res.status(500).json({
            success: false,
            message: 'Failed to send message',
            error: error.message
        });
    }
};

/**
 * Send an image to a WhatsApp number
 */
exports.sendImage = async (req, res) => {
    if (!whatsappClient || !whatsappClient.isReady) {
        return res.status(400).json({
            success: false,
            message: 'WhatsApp client not connected'
        });
    }

    const { phone, imageUrl, caption } = req.body;

    if (!imageUrl) {
        return res.status(400).json({
            success: false,
            message: 'Image URL is required'
        });
    }

    try {
        // Formatar número para padrão internacional
        const formattedPhone = formatPhoneNumber(phone);
        
        // Enviar imagem
        const response = await whatsappClient.sendMessage(
            `${formattedPhone}@c.us`, 
            { url: imageUrl, caption: caption || '' }
        );
        
        return res.json({
            success: true,
            data: {
                messageId: response.id._serialized,
                timestamp: new Date().toISOString()
            }
        });
    } catch (error) {
        console.error('Error sending image:', error);
        return res.status(500).json({
            success: false,
            message: 'Failed to send image',
            error: error.message
        });
    }
};

/**
 * Send a file to a WhatsApp number
 */
exports.sendFile = async (req, res) => {
    if (!whatsappClient || !whatsappClient.isReady) {
        return res.status(400).json({
            success: false,
            message: 'WhatsApp client not connected'
        });
    }

    const { phone, fileUrl, fileName } = req.body;

    if (!fileUrl) {
        return res.status(400).json({
            success: false,
            message: 'File URL is required'
        });
    }

    try {
        // Formatar número para padrão internacional
        const formattedPhone = formatPhoneNumber(phone);
        
        // Enviar arquivo
        const response = await whatsappClient.sendMessage(
            `${formattedPhone}@c.us`, 
            { url: fileUrl, filename: fileName || 'file' }
        );
        
        return res.json({
            success: true,
            data: {
                messageId: response.id._serialized,
                timestamp: new Date().toISOString()
            }
        });
    } catch (error) {
        console.error('Error sending file:', error);
        return res.status(500).json({
            success: false,
            message: 'Failed to send file',
            error: error.message
        });
    }
};

/**
 * Format phone number to international format
 * @param {string} phone - Phone number to format
 * @returns {string} Formatted phone number
 */
function formatPhoneNumber(phone) {
    // Remove caracteres não numéricos
    let cleaned = phone.replace(/\D/g, '');
    
    // Remove o + inicial se existir
    if (cleaned.startsWith('+')) {
        cleaned = cleaned.substring(1);
    }
    
    // Remove o 0 inicial do DDD se existir (formato brasileiro)
    if (cleaned.length === 13 && cleaned.startsWith('550')) {
        cleaned = '55' + cleaned.substring(3);
    }
    
    // Adiciona 55 (Brasil) se não tiver código do país
    if (cleaned.length === 11 || cleaned.length === 10) {
        cleaned = '55' + cleaned;
    }
    
    return cleaned;
}

