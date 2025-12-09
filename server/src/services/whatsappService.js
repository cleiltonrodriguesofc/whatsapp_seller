
const wppconnect = require('@wppconnect-team/wppconnect');
const fs = require('fs');
const path = require('path');

class WhatsAppService {
  constructor() {
    this.client = null;
    this.io = null; // Socket.io instance
  }

  setSocketIO(io) {
    this.io = io;
  }

  async initialize() {
    try {
      this.client = await wppconnect.create({
        session: 'whatsapp-sales-agent',
        catchQR: (base64Qr, asciiQR) => {
          console.log('QR Code received');
          if (this.io) {
            this.io.emit('qr', base64Qr);
          }
        },
        statusFind: (statusSession, session) => {
          console.log('Status Session: ', statusSession);
          if (this.io) {
            this.io.emit('status', statusSession);
          }
        },
        headless: true,
        devtools: false,
        useChrome: true,
        debug: false,
        logQR: true,
        browserArgs: [
          '--no-sandbox',
          '--disable-setuid-sandbox',
          '--disable-dev-shm-usage',
          '--disable-accelerated-2d-canvas',
          '--no-first-run',
          '--no-zygote',
          '--single-process', // Important for some environments
          '--disable-gpu'
        ],
        disableWelcome: true,
        updatesLog: false,
        autoClose: false,
      });

      this.setupListeners();
      return this.client;
    } catch (error) {
      console.error('Error initializing WhatsApp:', error);
      throw error;
    }
  }

  setupListeners() {
    if (!this.client) return;

    this.client.onStateChange((state) => {
      console.log('State Changed:', state);
      if (this.io) {
        this.io.emit('connection-status', state);
      }
    });

    this.client.onMessage((message) => {
        // Handle incoming messages
        if (this.io) {
            this.io.emit('message', message);
        }
    });
  }
  
  async getClient() {
    if (!this.client) {
      await this.initialize();
    }
    return this.client;
  }
}

module.exports = new WhatsAppService();
