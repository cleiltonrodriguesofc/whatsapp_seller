const Message = require('../../models/message');
const logger = require('../../utils/logger');
const { isOperatingHours, getCurrentDelay } = require('../../utils/helpers');

// Queue for messages
let messageQueue = [];
let isProcessing = false;

// Track last message time per contact
const lastMessageTime = new Map();
// Track last message time overall
let lastMessageSentTime = null;

// Constants from environment variables
const CONTACT_INTERVAL_MS = parseInt(process.env.CONTACT_INTERVAL_MS || '15000');
const SAME_CONTACT_INTERVAL_MS = parseInt(process.env.SAME_CONTACT_INTERVAL_MS || '2000');

/**
 * add message to queue
 * @param {Object} messageData - message data
 */
const addToMessageQueue = (messageData) => {
  // Add priority if not specified
  if (!messageData.options) {
    messageData.options = {};
  }
  
  if (!messageData.options.priority) {
    messageData.options.priority = 'normal';
  }
  
  // Add timestamp
  messageData.queuedAt = Date.now();
  
  // Add to queue based on priority
  if (messageData.options.priority === 'high') {
    // High priority messages go to the front
    messageQueue.unshift(messageData);
  } else {
    // Normal and low priority messages go to the back
    messageQueue.push(messageData);
  }
  
  logger.info(`Added message to queue. Queue length: ${messageQueue.length}`);
  
  // Start processing if not already running
  if (!isProcessing) {
    processQueue();
  }
};

/**
 * process message queue
 */
const processQueue = async () => {
  if (isProcessing || messageQueue.length === 0) {
    return;
  }
  
  isProcessing = true;
  
  try {
    // Check if we're in operating hours
    if (!isOperatingHours()) {
      logger.info('Outside operating hours. Queue processing paused.');
      isProcessing = false;
      
      // Schedule next check at start of next operating window
      const nextCheckTime = getNextOperatingWindowStart();
      setTimeout(processQueue, nextCheckTime - Date.now());
      return;
    }
    
    // Get next message
    const messageData = messageQueue[0];
    const { to, type } = messageData;
    
    // Calculate delays
    const now = Date.now();
    const contactLastMessageTime = lastMessageTime.get(to) || 0;
    const timeSinceLastMessageToContact = now - contactLastMessageTime;
    const timeSinceLastMessageOverall = lastMessageSentTime ? now - lastMessageSentTime : CONTACT_INTERVAL_MS + 1;
    
    // Check if we need to wait
    let waitTime = 0;
    
    // Check interval between messages to same contact
    if (timeSinceLastMessageToContact < SAME_CONTACT_INTERVAL_MS) {
      waitTime = Math.max(waitTime, SAME_CONTACT_INTERVAL_MS - timeSinceLastMessageToContact);
    }
    
    // Check interval between messages to different contacts
    if (timeSinceLastMessageOverall < CONTACT_INTERVAL_MS) {
      waitTime = Math.max(waitTime, CONTACT_INTERVAL_MS - timeSinceLastMessageOverall);
    }
    
    if (waitTime > 0) {
      // Need to wait before sending
      logger.info(`Waiting ${waitTime}ms before sending next message`);
      setTimeout(processQueue, waitTime);
      isProcessing = false;
      return;
    }
    
    // Remove message from queue
    messageQueue.shift();
    
    // Send message
    const { executeTextMessageSend, executeMediaMessageSend } = require('../whatsapp/whatsappService');
    
    if (type === 'text') {
      await executeTextMessageSend(messageData);
    } else if (type === 'media') {
      await executeMediaMessageSend(messageData);
    }
    
    // Update tracking
    lastMessageTime.set(to, Date.now());
    lastMessageSentTime = Date.now();
    
    // Continue processing queue
    isProcessing = false;
    
    // Add small delay to avoid CPU spinning
    setTimeout(processQueue, 100);
  } catch (error) {
    logger.error(`Error processing message queue: ${error.message}`);
    
    // Move failed message to end of queue for retry
    if (messageQueue.length > 0) {
      const failedMessage = messageQueue.shift();
      failedMessage.retryCount = (failedMessage.retryCount || 0) + 1;
      
      // Only retry up to 3 times
      if (failedMessage.retryCount <= 3) {
        messageQueue.push(failedMessage);
      } else {
        logger.error(`Message to ${failedMessage.to} failed after 3 retries`);
        
        // Update message record with error
        if (failedMessage.messageRecord) {
          failedMessage.messageRecord.status = 'failed';
          failedMessage.messageRecord.errorMessage = 'Failed after 3 retries';
          failedMessage.messageRecord.save().catch(err => {
            logger.error(`Error updating message record: ${err.message}`);
          });
        }
      }
    }
    
    // Continue processing queue after a delay
    isProcessing = false;
    setTimeout(processQueue, 5000);
  }
};

/**
 * get next operating window start time
 */
const getNextOperatingWindowStart = () => {
  const now = new Date();
  const startHour = parseInt(process.env.OPERATION_START_HOUR || '7');
  
  // If we're before today's start time, return today's start time
  if (now.getHours() < startHour) {
    const startTime = new Date(now);
    startTime.setHours(startHour, 0, 0, 0);
    return startTime.getTime();
  }
  
  // Otherwise, return tomorrow's start time
  const tomorrow = new Date(now);
  tomorrow.setDate(tomorrow.getDate() + 1);
  tomorrow.setHours(startHour, 0, 0, 0);
  return tomorrow.getTime();
};

/**
 * get queue status
 */
const getQueueStatus = () => {
  return {
    queueLength: messageQueue.length,
    isProcessing,
    nextMessageEstimate: estimateNextMessageTime()
  };
};

/**
 * estimate time until next message will be sent
 */
const estimateNextMessageTime = () => {
  if (messageQueue.length === 0) {
    return null;
  }
  
  if (!isOperatingHours()) {
    return getNextOperatingWindowStart();
  }
  
  const now = Date.now();
  const nextMessage = messageQueue[0];
  const { to } = nextMessage;
  
  const contactLastMessageTime = lastMessageTime.get(to) || 0;
  const timeSinceLastMessageToContact = now - contactLastMessageTime;
  const timeSinceLastMessageOverall = lastMessageSentTime ? now - lastMessageSentTime : CONTACT_INTERVAL_MS + 1;
  
  let waitTime = 0;
  
  // Check interval between messages to same contact
  if (timeSinceLastMessageToContact < SAME_CONTACT_INTERVAL_MS) {
    waitTime = Math.max(waitTime, SAME_CONTACT_INTERVAL_MS - timeSinceLastMessageToContact);
  }
  
  // Check interval between messages to different contacts
  if (timeSinceLastMessageOverall < CONTACT_INTERVAL_MS) {
    waitTime = Math.max(waitTime, CONTACT_INTERVAL_MS - timeSinceLastMessageOverall);
  }
  
  return now + waitTime;
};

/**
 * clear queue for a specific contact
 * @param {string} contactNumber - contact phone number
 */
const clearQueueForContact = (contactNumber) => {
  const initialLength = messageQueue.length;
  messageQueue = messageQueue.filter(msg => msg.to !== contactNumber);
  
  const removedCount = initialLength - messageQueue.length;
  logger.info(`Removed ${removedCount} messages for contact ${contactNumber} from queue`);
  
  return removedCount;
};

module.exports = {
  addToMessageQueue,
  processQueue,
  getQueueStatus,
  clearQueueForContact
};
