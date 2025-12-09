const mongoose = require('mongoose');
const Schema = mongoose.Schema;

// Schema for bulk message batches
const batchMessageSchema = new Schema({
  batchId: {
    type: String,
    required: true,
    unique: true
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
  status: {
    type: String,
    enum: ['pending', 'in_progress', 'completed', 'failed', 'cancelled'],
    default: 'pending'
  },
  scheduledTime: {
    type: Date
  },
  completedAt: {
    type: Date
  },
  totalMessages: {
    type: Number,
    default: 0
  },
  sentCount: {
    type: Number,
    default: 0
  },
  deliveredCount: {
    type: Number,
    default: 0
  },
  readCount: {
    type: Number,
    default: 0
  },
  failedCount: {
    type: Number,
    default: 0
  },
  recipients: [{
    to: {
      type: String,
      required: true
    },
    messageId: {
      type: String
    },
    status: {
      type: String,
      enum: ['queued', 'sent', 'delivered', 'read', 'failed'],
      default: 'queued'
    }
  }],
  options: {
    type: Object,
    default: {
      priority: 'low',
      simulate_typing: true
    }
  }
}, { timestamps: true });

// Indexes for better query performance
batchMessageSchema.index({ batchId: 1 });
batchMessageSchema.index({ status: 1 });
batchMessageSchema.index({ scheduledTime: 1 });

const BatchMessage = mongoose.model('BatchMessage', batchMessageSchema);

module.exports = BatchMessage;
