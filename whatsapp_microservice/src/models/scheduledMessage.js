const mongoose = require('mongoose');
const Schema = mongoose.Schema;

// Schema for scheduled messages
const scheduledMessageSchema = new Schema({
  scheduleId: {
    type: String,
    required: true,
    unique: true
  },
  to: {
    type: String,
    required: true
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
  scheduledTime: {
    type: Date,
    required: true
  },
  status: {
    type: String,
    enum: ['pending', 'sent', 'cancelled', 'failed'],
    default: 'pending'
  },
  sentMessageId: {
    type: String
  },
  errorMessage: {
    type: String
  },
  options: {
    type: Object,
    default: {
      priority: 'normal',
      simulate_typing: true
    }
  }
}, { timestamps: true });

// Indexes for better query performance
scheduledMessageSchema.index({ scheduleId: 1 });
scheduledMessageSchema.index({ status: 1, scheduledTime: 1 });
scheduledMessageSchema.index({ to: 1, status: 1 });

const ScheduledMessage = mongoose.model('ScheduledMessage', scheduledMessageSchema);

module.exports = ScheduledMessage;
