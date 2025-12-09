/**
 * Auth Controller
 * Handles authentication operations
 */

// Referência ao cliente WhatsApp (será injetado pelo app.js)
let whatsappClient;

// Exporta função para injetar o cliente WhatsApp
exports.setWhatsappClient = (client) => {
    whatsappClient = client;
};

/**
 * Logout from WhatsApp Web
 */
exports.logout = async (req, res) => {
    if (!whatsappClient) {
        return res.status(400).json({
            success: false,
            message: 'WhatsApp client not initialized'
        });
    }

    try {
        await whatsappClient.logout();
        
        return res.json({
            success: true,
            message: 'Logged out successfully'
        });
    } catch (error) {
        console.error('Error logging out:', error);
        return res.status(500).json({
            success: false,
            message: 'Failed to logout',
            error: error.message
        });
    }
};

