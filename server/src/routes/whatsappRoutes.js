
const express = require('express');
const router = express.Router();
const whatsappController = require('../controllers/whatsappController');

router.get('/status', whatsappController.getStatus);
router.post('/send', whatsappController.sendMessage);
router.get('/contacts', whatsappController.getContacts);

module.exports = router;
