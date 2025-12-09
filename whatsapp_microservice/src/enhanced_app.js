const express = require('express');
const cors = require('cors');
const { Client, LocalAuth } = require('whatsapp-web.js');
const qrcode = require('qrcode');

const app = express();
const PORT = process.env.PORT || 3001;

// middleware
app.use(cors());
app.use(express.json());

// global state
let client = null;
let qrCodeData = null;
let isConnected = false;
let connectionStatus = 'disconnected';
let conversations = [];
let contacts = [];

// initialize whatsapp client
function initializeWhatsApp() {
    console.log('Initializing WhatsApp client...');
    
    client = new Client({
        authStrategy: new LocalAuth({
            clientId: "whatsapp-sales-agent"
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

    // event listeners
    client.on('qr', async (qr) => {
        console.log('QR Code received');
        qrCodeData = qr;
        connectionStatus = 'qr_ready';
        
        try {
            const qrImage = await qrcode.toDataURL(qr);
            console.log('QR Code converted to base64');
        } catch (err) {
            console.error('Error generating QR Code:', err);
        }
    });

    client.on('ready', async () => {
        console.log('WhatsApp client connected!');
        isConnected = true;
        connectionStatus = 'connected';
        qrCodeData = null;
        
        // load conversations and contacts
        await loadConversations();
        await loadContacts();
    });

    client.on('authenticated', () => {
        console.log('Client authenticated');
        connectionStatus = 'authenticated';
    });

    client.on('auth_failure', (msg) => {
        console.error('Authentication failed:', msg);
        connectionStatus = 'auth_failed';
    });

    client.on('disconnected', (reason) => {
        console.log('Client disconnected:', reason);
        isConnected = false;
        connectionStatus = 'disconnected';
        qrCodeData = null;
        conversations = [];
        contacts = [];
    });

    // listen for new messages
    client.on('message', async (message) => {
        console.log('New message received:', message.body);
        await updateConversations();
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
        if (!client || !isConnected) return;
        
        console.log('Loading conversations...');
        const chats = await client.getChats();
        
        conversations = await Promise.all(chats.slice(0, 20).map(async (chat) => {
            try {
                const messages = await chat.fetchMessages({ limit: 10 });
                const contact = await chat.getContact();
                
                return {
                    id: chat.id._serialized,
                    name: chat.name || contact.pushname || contact.number,
                    isGroup: chat.isGroup,
                    unreadCount: chat.unreadCount,
                    lastMessage: messages[0] ? {
                        body: messages[0].body,
                        timestamp: messages[0].timestamp,
                        fromMe: messages[0].fromMe
                    } : null,
                    messages: messages.map(msg => ({
                        id: msg.id._serialized,
                        body: msg.body,
                        timestamp: msg.timestamp,
                        fromMe: msg.fromMe,
                        type: msg.type,
                        author: msg.author
                    }))
                };
            } catch (error) {
                console.error('Error processing chat:', error);
                return null;
            }
        }));
        
        // filter out null conversations
        conversations = conversations.filter(conv => conv !== null);
        console.log(`Loaded ${conversations.length} conversations`);
        
    } catch (error) {
        console.error('Error loading conversations:', error);
    }
}

// load contacts from whatsapp
async function loadContacts() {
    try {
        if (!client || !isConnected) return;
        
        console.log('Loading contacts...');
        const contactList = await client.getContacts();
        
        contacts = contactList.slice(0, 50).map(contact => ({
            id: contact.id._serialized,
            name: contact.name || contact.pushname || contact.number,
            number: contact.number,
            isMyContact: contact.isMyContact,
            profilePicUrl: contact.profilePicUrl
        }));
        
        console.log(`Loaded ${contacts.length} contacts`);
        
    } catch (error) {
        console.error('Error loading contacts:', error);
    }
}

// update conversations when new message arrives
async function updateConversations() {
    try {
        await loadConversations();
    } catch (error) {
        console.error('Error updating conversations:', error);
    }
}

// get messages from specific chat
async function getChatMessages(chatId, limit = 50) {
    try {
        if (!client || !isConnected) {
            throw new Error('WhatsApp not connected');
        }
        
        const chat = await client.getChatById(chatId);
        const messages = await chat.fetchMessages({ limit });
        
        return messages.map(msg => ({
            id: msg.id._serialized,
            body: msg.body,
            timestamp: msg.timestamp,
            fromMe: msg.fromMe,
            type: msg.type,
            author: msg.author,
            hasMedia: msg.hasMedia
        }));
        
    } catch (error) {
        console.error('Error getting chat messages:', error);
        throw error;
    }
}

// api routes
app.get('/status', async (req, res) => {
    try {
        let qrImage = null;
        
        if (qrCodeData && connectionStatus === 'qr_ready') {
            qrImage = await qrcode.toDataURL(qrCodeData);
        }
        
        res.json({
            status: connectionStatus,
            connected: isConnected,
            qr_code: qrImage,
            timestamp: new Date().toISOString(),
            conversations_count: conversations.length,
            contacts_count: contacts.length
        });
    } catch (error) {
        console.error('Error getting status:', error);
        res.status(500).json({
            error: 'Internal server error',
            status: connectionStatus,
            connected: false
        });
    }
});

app.get('/api/status', async (req, res) => {
    try {
        let qrImage = null;
        
        if (qrCodeData && connectionStatus === 'qr_ready') {
            qrImage = await qrcode.toDataURL(qrCodeData);
        }
        
        res.json({
            status: connectionStatus,
            connected: isConnected,
            qr_code: qrImage,
            timestamp: new Date().toISOString(),
            conversations_count: conversations.length,
            contacts_count: contacts.length
        });
    } catch (error) {
        console.error('Error getting status:', error);
        res.status(500).json({
            error: 'Internal server error',
            status: connectionStatus,
            connected: false
        });
    }
});

app.get('/api/conversations', async (req, res) => {
    try {
        if (!isConnected) {
            return res.status(400).json({
                error: 'WhatsApp not connected'
            });
        }
        
        // refresh conversations
        await loadConversations();
        
        res.json({
            conversations: conversations,
            total: conversations.length
        });
        
    } catch (error) {
        console.error('Error getting conversations:', error);
        res.status(500).json({
            error: 'Error loading conversations',
            details: error.message
        });
    }
});

app.get('/api/conversations/:chatId/messages', async (req, res) => {
    try {
        if (!isConnected) {
            return res.status(400).json({
                error: 'WhatsApp not connected'
            });
        }
        
        const { chatId } = req.params;
        const limit = parseInt(req.query.limit) || 50;
        
        const messages = await getChatMessages(chatId, limit);
        
        res.json({
            messages: messages,
            total: messages.length
        });
        
    } catch (error) {
        console.error('Error getting chat messages:', error);
        res.status(500).json({
            error: 'Error loading messages',
            details: error.message
        });
    }
});

app.get('/api/contacts', async (req, res) => {
    try {
        if (!isConnected) {
            return res.status(400).json({
                error: 'WhatsApp not connected'
            });
        }
        
        // refresh contacts
        await loadContacts();
        
        res.json({
            contacts: contacts,
            total: contacts.length
        });
        
    } catch (error) {
        console.error('Error getting contacts:', error);
        res.status(500).json({
            error: 'Error loading contacts',
            details: error.message
        });
    }
});

app.post('/api/send-message', async (req, res) => {
    try {
        if (!isConnected) {
            return res.status(400).json({
                error: 'WhatsApp not connected'
            });
        }

        const { chatId, phone, message } = req.body;
        
        if (!message) {
            return res.status(400).json({
                error: 'Message is required'
            });
        }

        let targetChatId;
        if (chatId) {
            targetChatId = chatId;
        } else if (phone) {
            targetChatId = phone.includes('@') ? phone : `${phone}@c.us`;
        } else {
            return res.status(400).json({
                error: 'Either chatId or phone is required'
            });
        }

        await client.sendMessage(targetChatId, message);
        
        // update conversations after sending message
        setTimeout(updateConversations, 1000);
        
        res.json({
            success: true,
            message: 'Message sent successfully'
        });
    } catch (error) {
        console.error('Error sending message:', error);
        res.status(500).json({
            error: 'Error sending message',
            details: error.message
        });
    }
});

app.post('/api/restart', (req, res) => {
    try {
        if (client) {
            client.destroy();
        }
        
        conversations = [];
        contacts = [];
        
        setTimeout(() => {
            initializeWhatsApp();
        }, 2000);
        
        res.json({
            success: true,
            message: 'Client restarted'
        });
    } catch (error) {
        console.error('Error restarting client:', error);
        res.status(500).json({
            error: 'Error restarting client'
        });
    }
});

// start server
app.listen(PORT, '0.0.0.0', () => {
    console.log(`WhatsApp Microservice running on port ${PORT}`);
    console.log(`Django API URL: http://localhost:8000`);
    
    // initialize whatsapp after 2 seconds
    setTimeout(() => {
        initializeWhatsApp();
    }, 2000);
});

// graceful shutdown
process.on('SIGINT', () => {
    console.log('Shutting down microservice...');
    if (client) {
        client.destroy();
    }
    process.exit(0);
});

process.on('SIGTERM', () => {
    console.log('Shutting down microservice...');
    if (client) {
        client.destroy();
    }
    process.exit(0);
});

