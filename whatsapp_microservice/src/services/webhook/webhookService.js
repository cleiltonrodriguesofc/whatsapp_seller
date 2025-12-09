const axios = require('axios');
const crypto = require('crypto');
const logger = require('../../utils/logger');
const WebhookConfig = require('../../models/webhookConfig');

/**
 * send notification to webhook
 * @param {Object} data - data to send
 */
const sendWebhookNotification = async (data) => {
  try {
    // Get webhook configuration
    const webhookConfig = await WebhookConfig.findOne({ status: 'active' });
    
    if (!webhookConfig) {
      logger.warn('No active webhook configuration found');
      return false;
    }
    
    // Generate signature
    const signature = generateSignature(data, webhookConfig.secret);
    
    // Send notification
    const response = await axios.post(webhookConfig.url, data, {
      headers: {
        'Content-Type': 'application/json',
        'X-Webhook-Signature': signature
      },
      timeout: 10000 // 10 second timeout
    });
    
    // Update webhook stats
    webhookConfig.lastSuccess = new Date();
    webhookConfig.errorCount = 0;
    await webhookConfig.save();
    
    logger.info(`Webhook notification sent successfully: ${response.status}`);
    return true;
  } catch (error) {
    logger.error(`Error sending webhook notification: ${error.message}`);
    
    // Update webhook error stats
    try {
      const webhookConfig = await WebhookConfig.findOne({ status: 'active' });
      if (webhookConfig) {
        webhookConfig.errorCount += 1;
        webhookConfig.lastError = error.message;
        webhookConfig.lastErrorTime = new Date();
        await webhookConfig.save();
      }
    } catch (statsError) {
      logger.error(`Error updating webhook stats: ${statsError.message}`);
    }
    
    return false;
  }
};

/**
 * generate HMAC signature for webhook
 * @param {Object} data - data to sign
 * @param {string} secret - webhook secret
 */
const generateSignature = (data, secret) => {
  const hmac = crypto.createHmac('sha256', secret);
  hmac.update(JSON.stringify(data));
  return hmac.digest('hex');
};

/**
 * configure webhook
 * @param {string} url - webhook URL
 * @param {Array} events - events to subscribe to
 * @param {string} secret - webhook secret
 */
const configureWebhook = async (url, events, secret) => {
  try {
    // Find existing configuration or create new one
    let webhookConfig = await WebhookConfig.findOne({});
    
    if (!webhookConfig) {
      webhookConfig = new WebhookConfig();
    }
    
    // Update configuration
    webhookConfig.url = url;
    webhookConfig.events = events;
    webhookConfig.secret = secret;
    webhookConfig.status = 'active';
    
    await webhookConfig.save();
    
    logger.info(`Webhook configured: ${url}`);
    return webhookConfig;
  } catch (error) {
    logger.error(`Error configuring webhook: ${error.message}`);
    throw error;
  }
};

/**
 * get webhook configuration
 */
const getWebhookConfig = async () => {
  try {
    const webhookConfig = await WebhookConfig.findOne({});
    return webhookConfig;
  } catch (error) {
    logger.error(`Error getting webhook configuration: ${error.message}`);
    throw error;
  }
};

/**
 * test webhook
 */
const testWebhook = async () => {
  try {
    const webhookConfig = await WebhookConfig.findOne({ status: 'active' });
    
    if (!webhookConfig) {
      throw new Error('No active webhook configuration found');
    }
    
    // Create test data
    const testData = {
      event: 'test',
      timestamp: Date.now(),
      message: 'This is a test webhook notification'
    };
    
    // Send test notification
    const startTime = Date.now();
    const result = await sendWebhookNotification(testData);
    const responseTime = Date.now() - startTime;
    
    return {
      success: result,
      status_code: result ? 200 : 0,
      response_time: responseTime,
      message: result ? 'Webhook tested successfully' : 'Webhook test failed'
    };
  } catch (error) {
    logger.error(`Error testing webhook: ${error.message}`);
    return {
      success: false,
      status_code: 0,
      response_time: 0,
      message: `Error: ${error.message}`
    };
  }
};

module.exports = {
  sendWebhookNotification,
  configureWebhook,
  getWebhookConfig,
  testWebhook
};
