const mongoose = require('mongoose');
const Schema = mongoose.Schema;

// Schema for WhatsApp messages
const messageSchema = new Schema({
  messageId: {
    type: String,
    required: true,
    unique: true
  },
  to: {
    type: String,
    required: true
  },
  from: {
    type: String,
    required: false // Not required for outbound messages
  },
  content: {
    type: String,
    required: true
  },
  messageType: {
    type: String,
    enum: ['text', 'image', 'audio', 'video', 'document', 'location'],
    default: 'text'
  },
  mediaUrl: {
    type: String
  },
  direction: {
    type: String,
    enum: ['inbound', 'outbound'],
    required: true
  },
  status: {
    type: String,
    enum: ['queued', 'sent', 'delivered', 'read', 'failed'],
    default: 'queued'
  },
  errorMessage: {
    type: String
  },
  timestamp: {
    type: Date,
    default: Date.now
  },
  deliveredAt: {
    type: Date
  },
  readAt: {
    type: Date
  },
  quotedMessageId: {
    type: String
  },
  batchId: {
    type: String,
    ref: 'BatchMessage'
  },
  scheduleId: {
    type: String,
    ref: 'ScheduledMessage'
  }
}, { timestamps: true });

// Indexes for better query performance
messageSchema.index({ messageId: 1 });
messageSchema.index({ to: 1, timestamp: -1 });
messageSchema.index({ status: 1 });
messageSchema.index({ direction: 1, timestamp: -1 });

const Message = mongoose.model('Message', messageSchema);

module.exports = Message;
