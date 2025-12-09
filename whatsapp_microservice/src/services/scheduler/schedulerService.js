const schedule = require('node-schedule');
const logger = require('../../utils/logger');
const ScheduledMessage = require('../../models/scheduledMessage');
const { sendTextMessage, sendMediaMessage } = require('../whatsapp/whatsappService');
const { isOperatingHours, getNextOperatingWindowStart } = require('../../utils/helpers');

// Store scheduled jobs
const scheduledJobs = new Map();

/**
 * initialize scheduler service
 */
const initializeScheduler = async () => {
  try {
    logger.info('Initializing scheduler service');
    
    // Load pending scheduled messages from database
    const pendingMessages = await ScheduledMessage.find({ status: 'pending' });
    logger.info(`Found ${pendingMessages.length} pending scheduled messages`);
    
    // Schedule each message
    pendingMessages.forEach(message => {
      scheduleMessage(message);
    });
    
    // Set up recurring job to check for new scheduled messages
    schedule.scheduleJob('*/5 * * * *', async () => {
      try {
        // Find any new scheduled messages that don't have jobs yet
        const newMessages = await ScheduledMessage.find({
          status: 'pending',
          scheduledTime: { $gt: new Date() }
        });
        
        newMessages.forEach(message => {
          if (!scheduledJobs.has(message.scheduleId)) {
            scheduleMessage(message);
          }
        });
      } catch (error) {
        logger.error(`Error checking for new scheduled messages: ${error.message}`);
      }
    });
    
    logger.info('Scheduler service initialized');
  } catch (error) {
    logger.error(`Error initializing scheduler service: ${error.message}`);
    throw error;
  }
};

/**
 * schedule a message for sending
 * @param {Object} message - scheduled message object
 */
const scheduleMessage = (message) => {
  try {
    // Check if already scheduled
    if (scheduledJobs.has(message.scheduleId)) {
      logger.info(`Message ${message.scheduleId} already scheduled`);
      return;
    }
    
    const scheduledTime = new Date(message.scheduledTime);
    
    // Don't schedule if time is in the past
    if (scheduledTime < new Date()) {
      logger.warn(`Scheduled time for message ${message.scheduleId} is in the past`);
      return;
    }
    
    // Create job
    const job = schedule.scheduleJob(scheduledTime, async () => {
      try {
        await executeScheduledMessage(message.scheduleId);
      } catch (error) {
        logger.error(`Error executing scheduled message ${message.scheduleId}: ${error.message}`);
      } finally {
        // Clean up job
        scheduledJobs.delete(message.scheduleId);
      }
    });
    
    // Store job reference
    scheduledJobs.set(message.scheduleId, job);
    
    logger.info(`Scheduled message ${message.scheduleId} for ${scheduledTime}`);
  } catch (error) {
    logger.error(`Error scheduling message ${message.scheduleId}: ${error.message}`);
  }
};

/**
 * execute a scheduled message
 * @param {string} scheduleId - ID of scheduled message
 */
const executeScheduledMessage = async (scheduleId) => {
  try {
    // Get message from database
    const message = await ScheduledMessage.findOne({ scheduleId });
    
    if (!message) {
      logger.warn(`Scheduled message ${scheduleId} not found`);
      return;
    }
    
    // Check if already sent or cancelled
    if (message.status !== 'pending') {
      logger.info(`Scheduled message ${scheduleId} is ${message.status}, not sending`);
      return;
    }
    
    // Check if we're in operating hours
    if (!isOperatingHours()) {
      logger.info(`Outside operating hours, rescheduling message ${scheduleId}`);
      
      // Reschedule for start of next operating window
      const nextWindow = getNextOperatingWindowStart();
      message.scheduledTime = new Date(nextWindow);
      await message.save();
      
      // Create new schedule
      scheduleMessage(message);
      return;
    }
    
    // Send message based on type
    let result;
    if (message.messageType === 'text') {
      result = await sendTextMessage(
        message.to,
        message.content,
        message.options || {}
      );
    } else {
      result = await sendMediaMessage(
        message.to,
        message.mediaUrl,
        message.content, // caption
        message.messageType,
        message.options || {}
      );
    }
    
    // Update message status
    message.status = 'sent';
    message.sentMessageId = result.messageId;
    await message.save();
    
    logger.info(`Executed scheduled message ${scheduleId}`);
  } catch (error) {
    logger.error(`Error executing scheduled message ${scheduleId}: ${error.message}`);
    
    // Update message status
    try {
      const message = await ScheduledMessage.findOne({ scheduleId });
      if (message) {
        message.status = 'failed';
        message.errorMessage = error.message;
        await message.save();
      }
    } catch (updateError) {
      logger.error(`Error updating scheduled message status: ${updateError.message}`);
    }
    
    throw error;
  }
};

/**
 * create a new scheduled message
 * @param {string} to - recipient phone number
 * @param {string} content - message content
 * @param {Date} scheduledTime - time to send message
 * @param {Object} options - sending options
 */
const createScheduledMessage = async (to, content, scheduledTime, options = {}) => {
  try {
    // Generate unique ID
    const scheduleId = `sched_${Date.now()}_${Math.random().toString(36).substring(2, 15)}`;
    
    // Create scheduled message record
    const scheduledMessage = new ScheduledMessage({
      scheduleId,
      to,
      content,
      messageType: 'text',
      scheduledTime,
      status: 'pending',
      options
    });
    
    await scheduledMessage.save();
    
    // Schedule the message
    scheduleMessage(scheduledMessage);
    
    logger.info(`Created scheduled message ${scheduleId} for ${scheduledTime}`);
    return scheduledMessage;
  } catch (error) {
    logger.error(`Error creating scheduled message: ${error.message}`);
    throw error;
  }
};

/**
 * create a new scheduled media message
 * @param {string} to - recipient phone number
 * @param {string} mediaUrl - URL of media
 * @param {string} caption - optional caption
 * @param {string} mediaType - type of media
 * @param {Date} scheduledTime - time to send message
 * @param {Object} options - sending options
 */
const createScheduledMediaMessage = async (to, mediaUrl, caption, mediaType, scheduledTime, options = {}) => {
  try {
    // Generate unique ID
    const scheduleId = `sched_${Date.now()}_${Math.random().toString(36).substring(2, 15)}`;
    
    // Create scheduled message record
    const scheduledMessage = new ScheduledMessage({
      scheduleId,
      to,
      content: caption || '',
      messageType: mediaType,
      mediaUrl,
      scheduledTime,
      status: 'pending',
      options
    });
    
    await scheduledMessage.save();
    
    // Schedule the message
    scheduleMessage(scheduledMessage);
    
    logger.info(`Created scheduled media message ${scheduleId} for ${scheduledTime}`);
    return scheduledMessage;
  } catch (error) {
    logger.error(`Error creating scheduled media message: ${error.message}`);
    throw error;
  }
};

/**
 * cancel a scheduled message
 * @param {string} scheduleId - ID of scheduled message
 */
const cancelScheduledMessage = async (scheduleId) => {
  try {
    // Get message from database
    const message = await ScheduledMessage.findOne({ scheduleId });
    
    if (!message) {
      logger.warn(`Scheduled message ${scheduleId} not found`);
      throw new Error('Scheduled message not found');
    }
    
    // Check if already sent or cancelled
    if (message.status !== 'pending') {
      logger.info(`Scheduled message ${scheduleId} is already ${message.status}`);
      return message;
    }
    
    // Cancel job if exists
    if (scheduledJobs.has(scheduleId)) {
      scheduledJobs.get(scheduleId).cancel();
      scheduledJobs.delete(scheduleId);
    }
    
    // Update message status
    message.status = 'cancelled';
    await message.save();
    
    logger.info(`Cancelled scheduled message ${scheduleId}`);
    return message;
  } catch (error) {
    logger.error(`Error cancelling scheduled message ${scheduleId}: ${error.message}`);
    throw error;
  }
};

/**
 * get scheduled message by ID
 * @param {string} scheduleId - ID of scheduled message
 */
const getScheduledMessage = async (scheduleId) => {
  try {
    const message = await ScheduledMessage.findOne({ scheduleId });
    
    if (!message) {
      logger.warn(`Scheduled message ${scheduleId} not found`);
      return null;
    }
    
    return message;
  } catch (error) {
    logger.error(`Error getting scheduled message ${scheduleId}: ${error.message}`);
    throw error;
  }
};

/**
 * list scheduled messages with pagination and filtering
 * @param {Object} filters - filter criteria
 * @param {number} page - page number
 * @param {number} limit - items per page
 */
const listScheduledMessages = async (filters = {}, page = 1, limit = 20) => {
  try {
    const query = { ...filters };
    const skip = (page - 1) * limit;
    
    const messages = await ScheduledMessage.find(query)
      .sort({ scheduledTime: 1 })
      .skip(skip)
      .limit(limit);
    
    const total = await ScheduledMessage.countDocuments(query);
    
    return {
      schedules: messages,
      pagination: {
        total,
        page,
        limit,
        pages: Math.ceil(total / limit)
      }
    };
  } catch (error) {
    logger.error(`Error listing scheduled messages: ${error.message}`);
    throw error;
  }
};

module.exports = {
  initializeScheduler,
  createScheduledMessage,
  createScheduledMediaMessage,
  cancelScheduledMessage,
  getScheduledMessage,
  listScheduledMessages
};
