
const express = require('express');
const router = express.Router();
const campaignsController = require('../controllers/campaignsController');

router.post('/', campaignsController.createCampaign);
router.get('/', campaignsController.getCampaigns);

module.exports = router;
