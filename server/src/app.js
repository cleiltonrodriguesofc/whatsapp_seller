
require('dotenv').config();
const express = require('express');
const http = require('http');
const { Server } = require('socket.io');
const cors = require('cors');
const whatsappService = require('./services/whatsappService');

const app = express();
const server = http.createServer(app);
const io = new Server(server, {
    cors: {
        origin: '*', // Allow all for development
        methods: ['GET', 'POST']
    }
});

const PORT = process.env.PORT || 3001;

// Middleware
app.use(cors());
app.use(express.json());

// Socket.IO
io.on('connection', (socket) => {
    console.log('New client connected:', socket.id);

    // Send current status if available? 
    // We might need to store the last known status in the service.

    socket.on('disconnect', () => {
        console.log('Client disconnected:', socket.id);
    });
});

// Initialize WhatsApp (prevent in test mode)
if (process.env.NODE_ENV !== 'test') {
    whatsappService.setSocketIO(io);
    whatsappService.initialize().then(() => {
        console.log('WhatsApp Agent Initialized');
    }).catch(err => {
        console.error('Failed to initialize WhatsApp Agent:', err);
    });
}

// Routes (Placeholder)
app.get('/', (req, res) => {
    res.send('WhatsApp Sales Agent API');
});

module.exports = { app, server, io };
