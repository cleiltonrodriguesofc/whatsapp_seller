const mongoose = require('mongoose');
const Schema = mongoose.Schema;

// Schema for webhook configuration
const webhookConfigSchema = new Schema({
  url: {
    type: String,
    required: true
  },
  secret: {
    type: String,
    required: true
  },
  events: {
    type: [String],
    default: ['message', 'status_update', 'connection_update']
  },
  status: {
    type: String,
    enum: ['active', 'inactive'],
    default: 'active'
  },
  lastSuccess: {
    type: Date
  },
  errorCount: {
    type: Number,
    default: 0
  },
  lastError: {
    type: String
  },
  lastErrorTime: {
    type: Date
  }
}, { timestamps: true });

const WebhookConfig = mongoose.model('WebhookConfig', webhookConfigSchema);

module.exports = WebhookConfig;
