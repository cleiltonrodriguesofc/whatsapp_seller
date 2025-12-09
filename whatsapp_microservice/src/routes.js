/**
 * API Routes for WhatsApp Microservice
 */
const express = require('express');
const router = express.Router();

// Controllers
const authController = require('./controllers/authController');
const statusController = require('./controllers/statusController');
const messageController = require('./controllers/messageController');
const webhookController = require('./controllers/webhookController');

// Middleware
const { validateMessage } = require('./middleware/validations');

// Status routes
router.get('/status', statusController.getStatus);
router.get('/qr', statusController.getQRCode);

// Message routes
router.post('/message/send', validateMessage, messageController.sendMessage);
router.post('/message/send-image', messageController.sendImage);
router.post('/message/send-file', messageController.sendFile);

// Webhook routes
router.post('/webhook/register', webhookController.register);
router.delete('/webhook/unregister', webhookController.unregister);

// Auth routes
router.post('/auth/logout', authController.logout);

module.exports = router;

