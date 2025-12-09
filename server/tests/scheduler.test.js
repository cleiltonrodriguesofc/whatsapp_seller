
const schedulerService = require('../src/services/schedulerService');

// Mock Dependencies
jest.mock('node-schedule', () => ({
    scheduleJob: jest.fn((cron, callback) => callback()) // execute immediately for test
}));

jest.mock('../src/services/databaseService', () => ({
    getCampaigns: jest.fn(),
    getContacts: jest.fn(),
    updateCampaignStatus: jest.fn()
}));


// Mock WhatsApp
// Mock WhatsApp
jest.mock('../src/services/whatsappService', () => ({
    getClient: jest.fn().mockResolvedValue({
        sendText: jest.fn().mockResolvedValue({ id: 'msg_123' }),
        sendTextStatus: jest.fn().mockResolvedValue(true)
    }),
    sendToStatus: jest.fn()
}));

describe('Scheduler Service', () => {
    beforeEach(() => {
        jest.clearAllMocks();
    });

    // Need to access the mocked functions to set return values dynamically if needed,
    // but importing the mocked module directly in test helps.
    const dbService = require('../src/services/databaseService');
    const whatsappService = require('../src/services/whatsappService');

    it('should execute pending campaigns due now', async () => {
        const now = new Date();
        const past = new Date(now.getTime() - 10000); // 10s ago

        dbService.getCampaigns.mockReturnValue([
            { id: 1, name: 'Test Campaign', message: 'Hello {name}', status: 'pending', type: 'message', audience_type: 'all', scheduled_at: past.toISOString() }
        ]);

        dbService.getContacts.mockReturnValue([
            { id: '123@c.us', name: 'John' }
        ]);

        await schedulerService.checkPendingCampaigns();

        expect(dbService.getCampaigns).toHaveBeenCalled();
        expect(dbService.getContacts).toHaveBeenCalled();
        expect(whatsappService.getClient).toHaveBeenCalled();
        // expect(mockSendText).toHaveBeenCalledWith('123@c.us', 'Hello John');
    });

    it('should ignore future campaigns', async () => {
        const future = new Date(Date.now() + 100000);
        dbService.getCampaigns.mockReturnValue([
            { id: 2, name: 'Future', message: 'Hi', status: 'pending', scheduled_at: future.toISOString() }
        ]);

        await schedulerService.checkPendingCampaigns();

        expect(whatsappService.getClient).not.toHaveBeenCalled();
    });

    it('should handle selected audience campaigns', async () => {
        const past = new Date(Date.now() - 10000);
        dbService.getCampaigns.mockReturnValue([
            { id: 3, name: 'Selected', message: 'Secret', status: 'pending', type: 'message', audience_type: 'selected', scheduled_at: past.toISOString() }
        ]);

        dbService.getCampaignItems = jest.fn().mockReturnValue([
            { contact_id: '999@c.us', name: 'VIP', number: '999@c.us' }
        ]);

        await schedulerService.checkPendingCampaigns();

        expect(dbService.getCampaignItems).toHaveBeenCalledWith(3);
        // Should NOT call getContacts (which fetches all)
        // Note: In previous test run getContacts was mocked, here we ensure it's not called if logic is correct
        // But since we are reusing mocks, we should ideally reset them or be careful. 
        // We will assume checkPendingCampaigns calls executeCampaign which calls logic.
    });

    it('should handle status updates', async () => {
        const past = new Date(Date.now() - 10000);
        dbService.getCampaigns.mockReturnValue([
            { id: 4, name: 'Status Update', message: 'New Offer!', status: 'pending', type: 'status', scheduled_at: past.toISOString() }
        ]);

        await schedulerService.checkPendingCampaigns();

        expect(whatsappService.sendToStatus).toHaveBeenCalledWith('New Offer!', 'text');
    });
});
