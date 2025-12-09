
const request = require('supertest');
const { app, server } = require('../src/app');

describe('GET /', () => {


    it('should return 200 OK and welcome message', async () => {
        const res = await request(app).get('/');
        expect(res.statusCode).toEqual(200);
        expect(res.text).toBe('WhatsApp Sales Agent API');
    });
});
