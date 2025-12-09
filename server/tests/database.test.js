
const fs = require('fs');
const path = require('path');
const dbPath = path.resolve(__dirname, '../../database.sqlite');

// Remove existing db before tests
if (fs.existsSync(dbPath)) {
    fs.unlinkSync(dbPath);
}

const dbService = require('../src/services/databaseService');

describe('Database Service', () => {
    afterAll(() => {
        // Cleanup
        if (fs.existsSync(dbPath)) {
            // We can't easily unlink if connection is open, better-sqlite3 keeps it open.
            // For now just leave it or use in-memory db for tests.
        }
    });

    test('should save and retrieve a contact', () => {
        const contact = {
            id: '12345@s.whatsapp.net',
            name: 'Test User',
            number: '12345',
            pushname: 'Test',
            isMyContact: 1,
            profilePicUrl: null
        };

        dbService.saveContact(contact);
        const contacts = dbService.getContacts();
        expect(contacts).toHaveLength(1);
        expect(contacts[0].id).toBe(contact.id);
    });

    test('should create and retrieve a campaign', () => {
        const campaign = {
            name: 'Test Campaign',
            message: 'Hello World',
            status: 'pending',
            type: 'message',
            audience_type: 'all',
            scheduled_at: new Date().toISOString()
        };

        dbService.createCampaign(campaign);
        const campaigns = dbService.getCampaigns();
        expect(campaigns.length).toBeGreaterThan(0);
        expect(campaigns[0].name).toBe('Test Campaign');
    });
});
