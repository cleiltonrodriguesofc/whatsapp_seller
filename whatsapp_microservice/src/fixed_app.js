const express = require('express');
const cors = require('cors');
const qrcode = require('qrcode');
const { Client, LocalAuth, MessageMedia } = require('whatsapp-web.js');
const axios = require('axios');

const app = express();
const port = process.env.PORT || 3001;

// middleware
app.use(cors());
app.use(express.json());

// global variables
let client = null;
let isConnected = false;
let connectionStatus = 'disconnected';
let qrCodeData = null;
let conversations = [];
let contacts = [];

// django api configuration
const DJANGO_API_URL = process.env.DJANGO_API_URL || 'http://localhost:8000';

// initialize whatsapp client
function initializeWhatsApp() {
    console.log('Initializing WhatsApp Client...');
    
    client = new Client({
        authStrategy: new LocalAuth({
            clientId: 'whatsapp-sales-agent'
        }),
        puppeteer: {
            headless: true,
            args: [
                '--no-sandbox',
                '--disable-setuid-sandbox',
                '--disable-dev-shm-usage',
                '--disable-accelerated-2d-canvas',
                '--no-first-run',
                '--no-zygote',
                '--single-process',
                '--disable-gpu'
            ]
        }
    });

    // qr code event
    client.on('qr', async (qr) => {
        console.log('QR Code received');
        try {
            qrCodeData = await qrcode.toDataURL(qr);
            connectionStatus = 'qr_ready';
        } catch (error) {
            console.error('Error generating QR code:', error);
        }
    });

    // ready event
    client.on('ready', async () => {
        console.log('WhatsApp Client is ready!');
        isConnected = true;
        connectionStatus = 'connected';
        qrCodeData = null;
        
        // load initial data
        await loadConversations();
        await loadContacts();
        
        console.log(`Loaded ${conversations.length} conversations and ${contacts.length} contacts`);
    });

    // authenticated event
    client.on('authenticated', () => {
        console.log('WhatsApp Client authenticated');
        connectionStatus = 'authenticated';
    });

    // auth failure event
    client.on('auth_failure', (msg) => {
        console.error('Authentication failed:', msg);
        connectionStatus = 'auth_failure';
        isConnected = false;
        qrCodeData = null;
    });

    // disconnected event
    client.on('disconnected', (reason) => {
        console.log('WhatsApp Client disconnected:', reason);
        isConnected = false;
        connectionStatus = 'disconnected';
        qrCodeData = null;
        conversations = [];
        contacts = [];
    });

    // listen for new messages
    client.on('message', async (message) => {
        console.log('New message received:', {
            from: message.from,
            body: message.body,
            fromMe: message.fromMe
        });
        
        // update conversations when new message arrives
        await updateConversations();
        
        // process message for AI response if not from me
        if (!message.fromMe) {
            await processIncomingMessage(message);
        }
    });

    // initialize client
    client.initialize().catch(err => {
        console.error('Error initializing client:', err);
        connectionStatus = 'error';
    });
}

// load conversations from whatsapp
async function loadConversations() {
    try {
        if (!client || !isConnected) {
            console.log('Client not ready for loading conversations');
            return;
        }
        
        console.log('Loading conversations...');
        const chats = await client.getChats();
        console.log(`Found ${chats.length} chats`);
        
        const conversationPromises = chats.slice(0, 30).map(async (chat) => {
            try {
                // get recent messages
                const messages = await chat.fetchMessages({ limit: 20 });
                
                // get contact info
                let contactName = chat.name;
                if (!contactName && !chat.isGroup) {
                    try {
                        const contact = await chat.getContact();
                        contactName = contact.pushname || contact.name || contact.number;
                    } catch (e) {
                        contactName = chat.id.user;
                    }
                }
                
                const conversation = {
                    id: chat.id._serialized,
                    name: contactName || 'Unknown',
                    isGroup: chat.isGroup,
                    unreadCount: chat.unreadCount || 0,
                    lastMessage: messages.length > 0 ? {
                        body: messages[0].body || '',
                        timestamp: messages[0].timestamp,
                        fromMe: messages[0].fromMe
                    } : null,
                    messages: messages.map(msg => ({
                        id: msg.id._serialized,
                        body: msg.body || '',
                        timestamp: msg.timestamp,
                        fromMe: msg.fromMe,
                        type: msg.type,
                        author: msg.author || msg.from
                    }))
                };
                
                return conversation;
            } catch (error) {
                console.error('Error processing chat:', chat.id._serialized, error.message);
                return null;
            }
        });
        
        const results = await Promise.allSettled(conversationPromises);
        conversations = results
            .filter(result => result.status === 'fulfilled' && result.value !== null)
            .map(result => result.value);
        
        console.log(`Successfully loaded ${conversations.length} conversations`);
        
    } catch (error) {
        console.error('Error loading conversations:', error);
        conversations = [];
    }
}

// update conversations (called when new message arrives)
async function updateConversations() {
    await loadConversations();
}

// load contacts from whatsapp
async function loadContacts() {
    try {
        if (!client || !isConnected) {
            console.log('Client not ready for loading contacts');
            return;
        }
        
        console.log('Loading contacts...');
        const contactList = await client.getContacts();
        
        contacts = contactList.slice(0, 100).map(contact => ({
            id: contact.id._serialized,
            name: contact.name || contact.pushname || contact.number,
            number: contact.number,
            isMyContact: contact.isMyContact,
            profilePicUrl: contact.profilePicUrl
        }));
        
        console.log(`Loaded ${contacts.length} contacts`);
        
    } catch (error) {
        console.error('Error loading contacts:', error);
        contacts = [];
    }
}

// process incoming message for AI response
async function processIncomingMessage(message) {
    try {
        console.log('Processing incoming message for AI response...');
        
        // get contact info
        const contact = await message.getContact();
        const chat = await message.getChat();
        
        // prepare message data for django
        const messageData = {
            whatsapp_id: message.from,
            contact_name: contact.pushname || contact.name || contact.number,
            message_body: message.body,
            message_type: message.type,
            timestamp: message.timestamp,
            is_group: chat.isGroup,
            chat_name: chat.name
        };
        
        // send to django for AI processing
        try {
            const response = await axios.post(`${DJANGO_API_URL}/api/whatsapp/process-message/`, messageData, {
                timeout: 10000,
                headers: {
                    'Content-Type': 'application/json'
                }
            });
            
            if (response.data.should_respond && response.data.ai_response) {
                console.log('Sending AI response:', response.data.ai_response);
                
                // send AI response back to whatsapp
                await client.sendMessage(message.from, response.data.ai_response);
                
                console.log('AI response sent successfully');
            }
            
        } catch (apiError) {
            console.error('Error calling Django API:', apiError.message);
        }
        
    } catch (error) {
        console.error('Error processing incoming message:', error);
    }
}

// get messages for specific chat
async function getChatMessages(chatId, limit = 50) {
    try {
        if (!client || !isConnected) {
            return [];
        }
        
        const chat = await client.getChatById(chatId);
        const messages = await chat.fetchMessages({ limit });
        
        return messages.map(msg => ({
            id: msg.id._serialized,
            body: msg.body || '',
            timestamp: msg.timestamp,
            fromMe: msg.fromMe,
            type: msg.type,
            author: msg.author || msg.from
        }));
        
    } catch (error) {
        console.error('Error getting chat messages:', error);
        return [];
    }
}

// send message
async function sendMessage(chatId, messageBody) {
    try {
        if (!client || !isConnected) {
            throw new Error('WhatsApp client not connected');
        }
        
        console.log('Sending message to:', chatId, 'Message:', messageBody);
        
        const message = await client.sendMessage(chatId, messageBody);
        
        // update conversations after sending
        setTimeout(() => updateConversations(), 1000);
        
        return {
            success: true,
            messageId: message.id._serialized,
            timestamp: message.timestamp
        };
        
    } catch (error) {
        console.error('Error sending message:', error);
        throw error;
    }
}

// routes
app.get('/status', (req, res) => {
    res.json({
        connected: isConnected,
        status: connectionStatus,
        qr_code: qrCodeData,
        timestamp: new Date().toISOString(),
        conversations_count: conversations.length,
        contacts_count: contacts.length
    });
});

app.get('/qr', (req, res) => {
    if (qrCodeData) {
        res.send(`<img src="${qrCodeData}" alt="QR Code" />`);
    } else {
        res.json({ error: 'QR Code not available' });
    }
});

// api routes
app.get('/api/status', (req, res) => {
    res.json({
        connected: isConnected,
        status: connectionStatus,
        qr_code: qrCodeData,
        timestamp: new Date().toISOString(),
        conversations_count: conversations.length,
        contacts_count: contacts.length
    });
});

app.get('/api/conversations', async (req, res) => {
    try {
        // refresh conversations if connected
        if (isConnected) {
            await loadConversations();
        }
        
        res.json({
            conversations: conversations,
            total: conversations.length
        });
    } catch (error) {
        console.error('Error getting conversations:', error);
        res.status(500).json({ error: 'Failed to get conversations' });
    }
});

app.get('/api/conversations/:chatId/messages', async (req, res) => {
    try {
        const { chatId } = req.params;
        const limit = parseInt(req.query.limit) || 50;
        
        const messages = await getChatMessages(chatId, limit);
        
        res.json({
            messages: messages,
            total: messages.length
        });
    } catch (error) {
        console.error('Error getting chat messages:', error);
        res.status(500).json({ error: 'Failed to get messages' });
    }
});

app.get('/api/contacts', (req, res) => {
    res.json({
        contacts: contacts,
        total: contacts.length
    });
});

app.post('/api/send-message', async (req, res) => {
    try {
        const { chat_id, message } = req.body;
        
        if (!chat_id || !message) {
            return res.status(400).json({ error: 'chat_id and message are required' });
        }
        
        const result = await sendMessage(chat_id, message);
        res.json(result);
        
    } catch (error) {
        console.error('Error in send message API:', error);
        res.status(500).json({ 
            success: false, 
            error: error.message 
        });
    }
});

app.post('/api/refresh', async (req, res) => {
    try {
        if (isConnected) {
            await loadConversations();
            await loadContacts();
        }
        
        res.json({
            success: true,
            conversations_count: conversations.length,
            contacts_count: contacts.length
        });
    } catch (error) {
        console.error('Error refreshing data:', error);
        res.status(500).json({ error: 'Failed to refresh data' });
    }
});

// health check
app.get('/health', (req, res) => {
    res.json({ 
        status: 'ok', 
        timestamp: new Date().toISOString(),
        whatsapp_status: connectionStatus
    });
});

// start server
app.listen(port, '0.0.0.0', () => {
    console.log(`WhatsApp Microservice running on port ${port}`);
    
    // initialize whatsapp client
    initializeWhatsApp();
});

// graceful shutdown
process.on('SIGINT', async () => {
    console.log('Shutting down gracefully...');
    if (client) {
        await client.destroy();
    }
    process.exit(0);
});

process.on('SIGTERM', async () => {
    console.log('Shutting down gracefully...');
    if (client) {
        await client.destroy();
    }
    process.exit(0);
});

