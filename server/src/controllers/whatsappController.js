
const whatsappService = require('../services/whatsappService');
const dbService = require('../services/databaseService');

exports.getStatus = async (req, res) => {
    try {
        const client = await whatsappService.getClient();
        if (!client) {
            return res.status(503).json({ status: 'initializing' });
        }
        const state = await client.getConnectionState();
        res.json({ status: state });
    } catch (error) {
        res.status(500).json({ error: 'Failed to get status' });
    }
}

exports.sendMessage = async (req, res) => {
    try {
        const { number, message } = req.body;
        if (!number || !message) {
            return res.status(400).json({ error: 'Number and message required' });
        }

        const client = await whatsappService.getClient();
        if (!client) {
            return res.status(503).json({ error: 'WhatsApp client not ready' });
        }

        // Ensure number format (basic check)
        const formattedNumber = number.includes('@c.us') ? number : `${number}@c.us`;

        const result = await client.sendText(formattedNumber, message);
        res.json({ success: true, messageId: result.id });
    } catch (error) {
        console.error('Error sending message:', error);
        res.status(500).json({ error: 'Failed to send message' });
    }
}

exports.getContacts = async (req, res) => {
    try {
        // First try DB
        let contacts = dbService.getContacts();

        // If empty, maybe fetch from WA (if connected) and sync?
        // For now just return what we have
        res.json(contacts);
    } catch (error) {
        console.error('Error fetching contacts:', error);
        res.status(500).json({ error: 'Internal server error' });
    }
}
