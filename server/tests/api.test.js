
const request = require('supertest');
const { app, server } = require('../src/app');

// Mock Services
jest.mock('../src/services/databaseService', () => ({
    getCampaigns: jest.fn().mockReturnValue([]),
    createCampaign: jest.fn().mockReturnValue({ lastInsertRowid: 1 }),
    getContacts: jest.fn().mockReturnValue([]),
    addCampaignItems: jest.fn()
}));

jest.mock('../src/services/whatsappService', () => ({
    getClient: jest.fn().mockResolvedValue({
        getConnectionState: jest.fn().mockResolvedValue('CONNECTED'),
        sendText: jest.fn().mockResolvedValue({ id: 'msg_123' })
    }),
    initialize: jest.fn().mockResolvedValue(true),
    setSocketIO: jest.fn()
}));


describe('API Endpoints', () => {
    /*
    // Server closing handled in app.test.js or global setup usually, 
    // but here we just need to test the app instance logic.
    */

    describe('GET /api/campaigns', () => {
        it('should return empty list initially', async () => {
            const res = await request(app).get('/api/campaigns');
            expect(res.statusCode).toEqual(200);
            expect(res.body).toEqual([]);
        });
    });

    describe('POST /api/campaigns', () => {
        it('should create a campaign', async () => {
            const res = await request(app).post('/api/campaigns').send({
                name: 'Test',
                message: 'Test Message'
            });
            expect(res.statusCode).toEqual(201);
            expect(res.body).toHaveProperty('id');
        });
    });

    describe('GET /api/whatsapp/status', () => {
        it('should return connection status', async () => {
            const res = await request(app).get('/api/whatsapp/status');
            expect(res.statusCode).toEqual(200);
            expect(res.body).toHaveProperty('status', 'CONNECTED');
        });
    });

    test('POST /api/campaigns should create a campaign with selected audience', async () => {
        const res = await request(app)
            .post('/api/campaigns')
            .send({
                name: 'VIP Campaign',
                message: 'Exclusive offer',
                type: 'message',
                audience_type: 'selected',
                selected_contacts: ['123@c.us', '456@c.us']
            });

        expect(res.statusCode).toBe(201);
        expect(res.body).toHaveProperty('id');
        expect(res.body.message).toBe('Campaign created');
    });
});
