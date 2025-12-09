
const schedule = require('node-schedule');
const dbService = require('./databaseService');
const whatsappService = require('./whatsappService');

class SchedulerService {
    constructor() {
        this.jobs = {};
    }

    initialize() {
        console.log('Initializing Scheduler Service...');
        // Poll for pending campaigns every minute
        schedule.scheduleJob('*/1 * * * *', () => {
            this.checkPendingCampaigns();
        });
    }

    async checkPendingCampaigns() {
        console.log('Checking for pending campaigns...');
        try {
            const campaigns = dbService.getCampaigns();
            const now = new Date();

            for (const campaign of campaigns) {
                if (campaign.status === 'pending') {
                    const scheduledTime = new Date(campaign.scheduled_at);

                    if (scheduledTime <= now) {
                        console.log(`Executing campaign: ${campaign.name}`);
                        await this.executeCampaign(campaign);
                    }
                }
            }
        } catch (error) {
            console.error('Error checking campaigns:', error);
        }
    }

    async executeCampaign(campaign) {
        console.log(`Starting execution of campaign ${campaign.id} (${campaign.name})`);

        // Mark as active/processing
        this.updateCampaignStatus(campaign.id, 'processing');

        try {
            const client = await whatsappService.getClient();
            if (!client) {
                console.log('WhatsApp client not ready, skipping campaign');
                return;
            }

            if (campaign.type === 'status') {
                console.log(`Posting Status for campaign "${campaign.name}"`);
                // For status we assume message is the content. If it was image it would be handled differently.
                // For now assuming text status from 'message' field.
                await whatsappService.sendToStatus(campaign.message, 'text');
                console.log('Status posted successfully');
            } else {
                // It's a message campaign
                let contacts = [];
                if (campaign.audience_type === 'selected') {
                    contacts = dbService.getCampaignItems(campaign.id);
                    console.log(`Targeting ${contacts.length} selected contacts`);
                } else {
                    contacts = dbService.getContacts();
                    console.log(`Targeting ALL ${contacts.length} contacts`);
                }

                for (const contact of contacts) {
                    try {
                        const number = contact.id || contact.number; // Ensure we have the ID/Number
                        // Simple template replacement
                        const message = campaign.message.replace('{name}', contact.name || 'Customer');

                        await client.sendText(number, message);
                        console.log(`Sent to ${number}`);

                        // Add delay to avoid ban
                        await new Promise(resolve => setTimeout(resolve, 2000 + Math.random() * 3000));
                    } catch (err) {
                        console.error(`Failed to send to ${contact.id}:`, err);
                    }
                }
            }

            // Mark as completed
            this.updateCampaignStatus(campaign.id, 'completed');
            console.log(`Campaign ${campaign.name} completed`);

        } catch (error) {
            console.error('Error executing campaign:', error);
            this.updateCampaignStatus(campaign.id, 'failed');
        }
    }

    updateCampaignStatus(id, status) {
        dbService.updateCampaignStatus(id, status);
    }
}

module.exports = new SchedulerService();
