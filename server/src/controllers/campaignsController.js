
const dbService = require('../services/databaseService');

exports.createCampaign = (req, res) => {
    try {
        const { name, message, type, scheduled_at, audience_type, selected_contacts } = req.body;

        if (!name || !message) {
            return res.status(400).json({ error: 'Name and message are required' });
        }

        const campaign = {
            name,
            message,
            type: type || 'message',
            status: 'pending',
            scheduled_at: scheduled_at || new Date().toISOString(),
            audience_type: audience_type || 'all'
        };

        const result = dbService.createCampaign(campaign);
        const campaignId = result.lastInsertRowid;

        if (audience_type === 'selected' && Array.isArray(selected_contacts) && selected_contacts.length > 0) {
            dbService.addCampaignItems(campaignId, selected_contacts);
        }

        res.status(201).json({
            message: 'Campaign created',
            id: campaignId
        });

    } catch (error) {
        console.error('Error creating campaign:', error);
        res.status(500).json({ error: 'Internal server error' });
    }
};

exports.getCampaigns = (req, res) => {
    try {
        const campaigns = dbService.getCampaigns();
        res.json(campaigns);
    } catch (error) {
        console.error('Error fetching campaigns:', error);
        res.status(500).json({ error: 'Internal server error' });
    }
};
