const wppconnect = require('@wppconnect-team/wppconnect');
const logger = require('../../utils/logger');
const Message = require('../../models/message');
const WebhookConfig = require('../../models/webhookConfig');
const { sendWebhookNotification } = require('../webhook/webhookService');
const { addToMessageQueue } = require('../queue/queueService');
const { generateRandomDelay } = require('../../utils/helpers');

// Store client instance
let client = null;
let connectionStatus = 'disconnected';
let qrCode = null;
let qrCodeExpiration = null;
let connectedPhone = null;

/**
 * initialize whatsapp connection
 */
const initializeWhatsApp = async () => {
  try {
    logger.info('Initializing WhatsApp connection');
    
    // Create client with session
    client = await wppconnect.create({
      session: 'whatsapp-session',
      catchQR: (base64Qr, asciiQR, attempts, urlCode) => {
        logger.info(`QR Code generated (attempt ${attempts})`);
        qrCode = base64Qr;
        // QR code expires in 2 minutes
        qrCodeExpiration = new Date(Date.now() + 2 * 60 * 1000);
      },
      statusFind: (statusSession, session) => {
        logger.info(`Status session: ${statusSession}`);
        connectionStatus = statusSession;
      },
      folderNameToken: './sessions',
      headless: true,
      logQR: false,
      useChrome: true,
      updatesLog: false,
      autoClose: 60000,
      browserArgs: [
        '--no-sandbox',
        '--disable-setuid-sandbox',
        '--disable-dev-shm-usage',
        '--disable-accelerated-2d-canvas',
        '--no-first-run',
        '--no-zygote',
        '--single-process',
        '--disable-gpu'
      ]
    });
    
    logger.info('WhatsApp client created');
    
    // Set up event listeners
    setupEventListeners();
    
    // Update connection status
    connectionStatus = 'connected';
    connectedPhone = await getConnectedPhone();
    
    // Notify via webhook
    notifyConnectionUpdate();
    
    return { status: connectionStatus, phone: connectedPhone };
  } catch (error) {
    logger.error(`Error initializing WhatsApp: ${error.message}`);
    connectionStatus = 'disconnected';
    throw error;
  }
};

/**
 * get connected phone number
 */
const getConnectedPhone = async () => {
  if (!client) return null;
  
  try {
    const info = await client.getHostDevice();
    return info.wid.user;
  } catch (error) {
    logger.error(`Error getting connected phone: ${error.message}`);
    return null;
  }
};

/**
 * setup event listeners for whatsapp client
 */
const setupEventListeners = () => {
  if (!client) return;
  
  // Message received event
  client.onMessage(async (message) => {
    try {
      logger.info(`Message received from ${message.from}`);
      
      // Skip messages from groups if needed
      if (message.isGroupMsg) {
        logger.info('Skipping group message');
        return;
      }
      
      // Process and store message
      await processIncomingMessage(message);
    } catch (error) {
      logger.error(`Error processing incoming message: ${error.message}`);
    }
  });
  
  // Message status update event
  client.onAck(async (ack) => {
    try {
      logger.info(`Message status update: ${ack.id._serialized} -> ${ack.ack}`);
      
      // Map WhatsApp ack status to our status
      const statusMap = {
        0: 'sent',
        1: 'sent',
        2: 'delivered',
        3: 'read',
        -1: 'failed'
      };
      
      const status = statusMap[ack.ack] || 'sent';
      
      // Update message status in database
      await updateMessageStatus(ack.id._serialized, status);
      
      // Notify via webhook
      notifyStatusUpdate(ack.id._serialized, status);
    } catch (error) {
      logger.error(`Error processing message status update: ${error.message}`);
    }
  });
  
  // Connection state changes
  client.onStateChange((state) => {
    logger.info(`Connection state changed: ${state}`);
    
    if (state === 'CONNECTED') {
      connectionStatus = 'connected';
      notifyConnectionUpdate();
    } else if (state === 'DISCONNECTED') {
      connectionStatus = 'disconnected';
      connectedPhone = null;
      notifyConnectionUpdate();
    }
  });
  
  // Disconnected event
  client.onDisconnected((reason) => {
    logger.info(`WhatsApp disconnected: ${reason}`);
    connectionStatus = 'disconnected';
    connectedPhone = null;
    notifyConnectionUpdate();
  });
};

/**
 * process incoming message
 * @param {Object} message - WhatsApp message object
 */
const processIncomingMessage = async (message) => {
  try {
    // Extract message details
    const messageId = message.id;
    const from = message.from;
    const to = message.to;
    const content = message.body || '';
    const timestamp = message.timestamp * 1000; // Convert to milliseconds
    
    // Determine message type
    let messageType = 'text';
    let mediaUrl = null;
    
    if (message.hasMedia) {
      if (message.type === 'image') messageType = 'image';
      else if (message.type === 'video') messageType = 'video';
      else if (message.type === 'audio') messageType = 'audio';
      else if (message.type === 'document') messageType = 'document';
      
      // Download and store media if needed
      // This would require additional implementation
    }
    
    // Create message record
    const newMessage = new Message({
      messageId: messageId,
      from: from,
      to: to,
      content: content,
      messageType: messageType,
      mediaUrl: mediaUrl,
      direction: 'inbound',
      status: 'delivered',
      timestamp: new Date(timestamp),
      deliveredAt: new Date()
    });
    
    await newMessage.save();
    logger.info(`Incoming message saved: ${messageId}`);
    
    // Notify via webhook
    await notifyNewMessage(newMessage);
    
    return newMessage;
  } catch (error) {
    logger.error(`Error processing incoming message: ${error.message}`);
    throw error;
  }
};

/**
 * send text message
 * @param {string} to - recipient phone number
 * @param {string} message - message content
 * @param {Object} options - sending options
 */
const sendTextMessage = async (to, message, options = {}) => {
  if (!client) {
    throw new Error('WhatsApp client not initialized');
  }
  
  try {
    // Format phone number
    const formattedNumber = formatPhoneNumber(to);
    
    // Create message record
    const messageRecord = new Message({
      messageId: `pending_${Date.now()}_${Math.random().toString(36).substring(2, 15)}`,
      to: formattedNumber,
      content: message,
      messageType: 'text',
      direction: 'outbound',
      status: 'queued',
      timestamp: new Date()
    });
    
    await messageRecord.save();
    
    // Add to message queue
    addToMessageQueue({
      type: 'text',
      to: formattedNumber,
      content: message,
      options: options,
      messageRecord: messageRecord
    });
    
    return messageRecord;
  } catch (error) {
    logger.error(`Error queueing text message: ${error.message}`);
    throw error;
  }
};

/**
 * send media message
 * @param {string} to - recipient phone number
 * @param {string} mediaUrl - URL of media
 * @param {string} caption - optional caption
 * @param {string} mediaType - type of media
 * @param {Object} options - sending options
 */
const sendMediaMessage = async (to, mediaUrl, caption = '', mediaType = 'image', options = {}) => {
  if (!client) {
    throw new Error('WhatsApp client not initialized');
  }
  
  try {
    // Format phone number
    const formattedNumber = formatPhoneNumber(to);
    
    // Create message record
    const messageRecord = new Message({
      messageId: `pending_${Date.now()}_${Math.random().toString(36).substring(2, 15)}`,
      to: formattedNumber,
      content: caption,
      messageType: mediaType,
      mediaUrl: mediaUrl,
      direction: 'outbound',
      status: 'queued',
      timestamp: new Date()
    });
    
    await messageRecord.save();
    
    // Add to message queue
    addToMessageQueue({
      type: 'media',
      to: formattedNumber,
      mediaUrl: mediaUrl,
      caption: caption,
      mediaType: mediaType,
      options: options,
      messageRecord: messageRecord
    });
    
    return messageRecord;
  } catch (error) {
    logger.error(`Error queueing media message: ${error.message}`);
    throw error;
  }
};

/**
 * actually send text message (called by queue processor)
 * @param {Object} messageData - message data from queue
 */
const executeTextMessageSend = async (messageData) => {
  if (!client) {
    throw new Error('WhatsApp client not initialized');
  }
  
  const { to, content, options, messageRecord } = messageData;
  
  try {
    // Simulate typing if requested
    if (options.simulate_typing) {
      await client.startTyping(to);
      const typingTime = options.typing_time || generateRandomDelay(content.length);
      await new Promise(resolve => setTimeout(resolve, typingTime));
      await client.stopTyping(to);
    }
    
    // Send message
    const result = await client.sendText(to, content);
    
    // Update message record with actual message ID
    messageRecord.messageId = result.id._serialized;
    messageRecord.status = 'sent';
    await messageRecord.save();
    
    logger.info(`Text message sent to ${to}: ${result.id._serialized}`);
    return result;
  } catch (error) {
    logger.error(`Error sending text message: ${error.message}`);
    
    // Update message record with error
    messageRecord.status = 'failed';
    messageRecord.errorMessage = error.message;
    await messageRecord.save();
    
    throw error;
  }
};

/**
 * actually send media message (called by queue processor)
 * @param {Object} messageData - message data from queue
 */
const executeMediaMessageSend = async (messageData) => {
  if (!client) {
    throw new Error('WhatsApp client not initialized');
  }
  
  const { to, mediaUrl, caption, mediaType, options, messageRecord } = messageData;
  
  try {
    // Simulate typing if requested
    if (options.simulate_typing) {
      await client.startTyping(to);
      const typingTime = options.typing_time || generateRandomDelay(caption.length);
      await new Promise(resolve => setTimeout(resolve, typingTime));
      await client.stopTyping(to);
    }
    
    let result;
    
    // Send based on media type
    switch (mediaType) {
      case 'image':
        result = await client.sendImage(to, mediaUrl, 'image', caption);
        break;
      case 'video':
        result = await client.sendVideoAsGif(to, mediaUrl, 'video', caption);
        break;
      case 'audio':
        result = await client.sendPtt(to, mediaUrl);
        break;
      case 'document':
        result = await client.sendFile(to, mediaUrl, 'document', caption);
        break;
      default:
        throw new Error(`Unsupported media type: ${mediaType}`);
    }
    
    // Update message record with actual message ID
    messageRecord.messageId = result.id._serialized;
    messageRecord.status = 'sent';
    await messageRecord.save();
    
    logger.info(`Media message sent to ${to}: ${result.id._serialized}`);
    return result;
  } catch (error) {
    logger.error(`Error sending media message: ${error.message}`);
    
    // Update message record with error
    messageRecord.status = 'failed';
    messageRecord.errorMessage = error.message;
    await messageRecord.save();
    
    throw error;
  }
};

/**
 * update message status in database
 * @param {string} messageId - message ID
 * @param {string} status - new status
 */
const updateMessageStatus = async (messageId, status) => {
  try {
    const message = await Message.findOne({ messageId: messageId });
    
    if (!message) {
      logger.warn(`Message not found for status update: ${messageId}`);
      return null;
    }
    
    message.status = status;
    
    if (status === 'delivered') {
      message.deliveredAt = new Date();
    } else if (status === 'read') {
      message.readAt = new Date();
    }
    
    await message.save();
    logger.info(`Updated message ${messageId} status to ${status}`);
    
    return message;
  } catch (error) {
    logger.error(`Error updating message status: ${error.message}`);
    throw error;
  }
};

/**
 * notify new message via webhook
 * @param {Object} message - message object
 */
const notifyNewMessage = async (message) => {
  try {
    const webhookData = {
      event: 'message',
      timestamp: Date.now(),
      message: {
        id: message.messageId,
        from: message.from,
        type: message.messageType,
        content: message.messageType === 'text' ? message.content : {
          caption: message.content,
          mime_type: getMimeType(message.messageType),
          filename: getFilenameFromUrl(message.mediaUrl),
          size: 0, // Would need to be determined
          url: message.mediaUrl
        },
        timestamp: message.timestamp.getTime()
      }
    };
    
    await sendWebhookNotification(webhookData);
  } catch (error) {
    logger.error(`Error sending webhook notification: ${error.message}`);
  }
};

/**
 * notify status update via webhook
 * @param {string} messageId - message ID
 * @param {string} status - message status
 */
const notifyStatusUpdate = async (messageId, status) => {
  try {
    const message = await Message.findOne({ messageId: messageId });
    
    if (!message) {
      logger.warn(`Message not found for webhook notification: ${messageId}`);
      return;
    }
    
    const webhookData = {
      event: 'status_update',
      timestamp: Date.now(),
      status: {
        message_id: messageId,
        status: status,
        to: message.to,
        timestamp: Date.now()
      }
    };
    
    await sendWebhookNotification(webhookData);
  } catch (error) {
    logger.error(`Error sending status webhook notification: ${error.message}`);
  }
};

/**
 * notify connection update via webhook
 */
const notifyConnectionUpdate = async () => {
  try {
    const webhookData = {
      event: 'connection_update',
      timestamp: Date.now(),
      connection: {
        status: connectionStatus,
        phone: connectedPhone
      }
    };
    
    await sendWebhookNotification(webhookData);
  } catch (error) {
    logger.error(`Error sending connection webhook notification: ${error.message}`);
  }
};

/**
 * get connection status
 */
const getStatus = async () => {
  return {
    status: connectionStatus,
    phone: connectedPhone,
    battery: await getBatteryLevel(),
    qr_pending: qrCode !== null && qrCodeExpiration > new Date(),
    uptime: client ? Math.floor((Date.now() - client.startTime) / 1000) : 0,
    version: '1.0.0'
  };
};

/**
 * get battery level
 */
const getBatteryLevel = async () => {
  if (!client || connectionStatus !== 'connected') return null;
  
  try {
    const batteryInfo = await client.getBatteryLevel();
    return batteryInfo.battery;
  } catch (error) {
    logger.error(`Error getting battery level: ${error.message}`);
    return null;
  }
};

/**
 * get QR code for authentication
 */
const getQrCode = () => {
  if (connectionStatus === 'connected') {
    return {
      qr_code: null,
      message: 'Already connected to WhatsApp',
      phone: connectedPhone
    };
  }
  
  if (!qrCode || !qrCodeExpiration || qrCodeExpiration < new Date()) {
    // Restart client to generate new QR code
    restartClient();
    
    return {
      qr_code: null,
      message: 'Generating new QR code, please try again in a few seconds',
      attempts: 0
    };
  }
  
  return {
    qr_code: qrCode,
    attempts: 1,
    expires_at: qrCodeExpiration.toISOString()
  };
};

/**
 * restart whatsapp client
 */
const restartClient = async () => {
  try {
    if (client) {
      await client.close();
    }
    
    connectionStatus = 'disconnected';
    connectedPhone = null;
    qrCode = null;
    qrCodeExpiration = null;
    
    // Start initialization process
    initializeWhatsApp();
  } catch (error) {
    logger.error(`Error restarting client: ${error.message}`);
    throw error;
  }
};

/**
 * logout from whatsapp
 */
const logout = async () => {
  try {
    if (!client) {
      return { success: true, message: 'Not connected' };
    }
    
    await client.logout();
    await client.close();
    
    connectionStatus = 'disconnected';
    connectedPhone = null;
    qrCode = null;
    qrCodeExpiration = null;
    client = null;
    
    return { success: true, message: 'Disconnected successfully' };
  } catch (error) {
    logger.error(`Error logging out: ${error.message}`);
    throw error;
  }
};

/**
 * format phone number to ensure it has country code
 * @param {string} phoneNumber - phone number to format
 */
const formatPhoneNumber = (phoneNumber) => {
  // Remove any non-digit characters
  let cleaned = phoneNumber.replace(/\D/g, '');
  
  // Ensure it has country code (default to Brazil +55 if none)
  if (cleaned.length <= 13 && !cleaned.startsWith('55')) {
    cleaned = '55' + cleaned;
  }
  
  // Add @c.us suffix if not present
  if (!phoneNumber.endsWith('@c.us')) {
    cleaned = cleaned + '@c.us';
  }
  
  return cleaned;
};

/**
 * get mime type based on message type
 * @param {string} messageType - type of message
 */
const getMimeType = (messageType) => {
  const mimeTypes = {
    image: 'image/jpeg',
    video: 'video/mp4',
    audio: 'audio/ogg',
    document: 'application/pdf'
  };
  
  return mimeTypes[messageType] || 'application/octet-stream';
};

/**
 * extract filename from url
 * @param {string} url - media URL
 */
const getFilenameFromUrl = (url) => {
  if (!url) return 'file';
  
  try {
    const urlObj = new URL(url);
    const pathname = urlObj.pathname;
    return pathname.substring(pathname.lastIndexOf('/') + 1);
  } catch (error) {
    return 'file';
  }
};

module.exports = {
  initializeWhatsApp,
  sendTextMessage,
  sendMediaMessage,
  executeTextMessageSend,
  executeMediaMessageSend,
  getStatus,
  getQrCode,
  logout,
  restartClient
};
