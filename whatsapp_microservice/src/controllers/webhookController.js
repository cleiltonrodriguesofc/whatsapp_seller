/**
 * Webhook Controller
 * Handles webhook registration and management
 */

// Armazena URLs de webhook registradas
const webhooks = new Set();

/**
 * Register a webhook URL
 */
exports.register = (req, res) => {
    const { url } = req.body;
    
    if (!url) {
        return res.status(400).json({
            success: false,
            message: 'Webhook URL is required'
        });
    }
    
    try {
        // Validar URL
        new URL(url);
        
        // Adicionar URL ao conjunto
        webhooks.add(url);
        
        return res.json({
            success: true,
            message: 'Webhook registered successfully',
            data: {
                url,
                registeredAt: new Date().toISOString()
            }
        });
    } catch (error) {
        return res.status(400).json({
            success: false,
            message: 'Invalid URL format'
        });
    }
};

/**
 * Unregister a webhook URL
 */
exports.unregister = (req, res) => {
    const { url } = req.body;
    
    if (!url) {
        return res.status(400).json({
            success: false,
            message: 'Webhook URL is required'
        });
    }
    
    // Remover URL do conjunto
    const removed = webhooks.delete(url);
    
    if (removed) {
        return res.json({
            success: true,
            message: 'Webhook unregistered successfully'
        });
    } else {
        return res.status(404).json({
            success: false,
            message: 'Webhook URL not found'
        });
    }
};

/**
 * Get all registered webhook URLs
 */
exports.getWebhooks = () => {
    return Array.from(webhooks);
};

