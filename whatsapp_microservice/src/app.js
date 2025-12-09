const express = require('express');
const cors = require('cors');
const axios = require('axios');
const { Client, LocalAuth } = require('whatsapp-web.js');
const qrcode = require('qrcode-terminal');
const routes = require('./routes');

// Controllers
const statusController = require('./controllers/statusController');
const messageController = require('./controllers/messageController');
const authController = require('./controllers/authController');

const app = express();
const PORT = process.env.PORT || 8081;
const DJANGO_API_URL = process.env.DJANGO_API_URL || 'http://localhost:8000';

// Estado do cliente
let isReady = false;
let qrCodeData = null;

// Middleware
app.use(cors());
app.use(express.json());

// WhatsApp Client
const client = new Client({
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

// Injetar cliente WhatsApp nos controllers
statusController.setWhatsappClient(client);
messageController.setWhatsappClient(client);
authController.setWhatsappClient(client);

// Eventos do WhatsApp
client.on('qr', (qr) => {
    console.log('QR Code received');
    qrCodeData = qr;
    statusController.setQRCode(qr);
    qrcode.generate(qr, { small: true });
});

client.on('ready', () => {
    console.log('WhatsApp Client is ready!');
    isReady = true;
    qrCodeData = null;
    statusController.setQRCode(null);
});

client.on('authenticated', () => {
    console.log('WhatsApp Client authenticated');
});

client.on('auth_failure', (msg) => {
    console.error('Authentication failed:', msg);
});

client.on('disconnected', (reason) => {
    console.log('WhatsApp Client disconnected:', reason);
    isReady = false;
});

// Processar mensagens recebidas
client.on('message', async (message) => {
    try {
        console.log('Message received:', message.body);
        
        const contact = await message.getContact();
        const chat = await message.getChat();
        
        // Enviar para Django API
        const response = await axios.post(`${DJANGO_API_URL}/api/webhook/`, {
            type: 'message',
            id: message.id._serialized,
            from: message.from,
            to: message.to,
            body: message.body,
            name: contact.name || contact.pushname || 'Unknown',
            timestamp: message.timestamp,
            isGroup: chat.isGroup,
            groupName: chat.isGroup ? chat.name : null
        });
        
        // Se Django retornou uma resposta, enviar de volta
        if (response.data.response) {
            await message.reply(response.data.response);
        }
        
        // Se é um comando que requer confirmação
        if (response.data.requires_confirmation) {
            console.log('Command detected, waiting for confirmation');
        }
        
    } catch (error) {
        console.error('Error processing message:', error.message);
        
        // Resposta de fallback em caso de erro
        try {
            await message.reply('Desculpe, ocorreu um erro temporário. Tente novamente em alguns instantes.');
        } catch (replyError) {
            console.error('Error sending fallback reply:', replyError.message);
        }
    }
});

// Rotas da API
app.use('/api', routes);

// Status do sistema
app.get('/status', (req, res) => {
    res.json({
        status: 'online',
        whatsapp_ready: isReady,
        qr_code: qrCodeData,
        timestamp: new Date().toISOString()
    });
});

// QR Code para autenticação
app.get('/qr', (req, res) => {
    if (qrCodeData) {
        res.json({
            qr_code: qrCodeData,
            status: 'waiting_scan'
        });
    } else if (isReady) {
        res.json({
            status: 'authenticated',
            message: 'WhatsApp is ready'
        });
    } else {
        res.json({
            status: 'initializing',
            message: 'WhatsApp client is initializing'
        });
    }
});

// Enviar mensagem
app.post('/send-message', async (req, res) => {
    try {
        if (!isReady) {
            return res.status(503).json({
                error: 'WhatsApp client not ready',
                status: 'not_ready'
            });
        }
        
        const { to, message, delay = 0 } = req.body;
        
        if (!to || !message) {
            return res.status(400).json({
                error: 'Missing required fields: to, message'
            });
        }
        
        // Aplicar delay se especificado (para mitigação de riscos)
        if (delay > 0) {
            await new Promise(resolve => setTimeout(resolve, delay * 1000));
        }
        
        // Formatar número de telefone
        const phoneNumber = to.includes('@c.us') ? to : `${to}@c.us`;
        
        // Enviar mensagem
        const sentMessage = await client.sendMessage(phoneNumber, message);
        
        res.json({
            success: true,
            message_id: sentMessage.id._serialized,
            to: phoneNumber,
            timestamp: new Date().toISOString()
        });
        
    } catch (error) {
        console.error('Error sending message:', error.message);
        res.status(500).json({
            error: 'Failed to send message',
            details: error.message
        });
    }
});

// Enviar mensagem para grupo
app.post('/send-group-message', async (req, res) => {
    try {
        if (!isReady) {
            return res.status(503).json({
                error: 'WhatsApp client not ready'
            });
        }
        
        const { groupName, message, delay = 0 } = req.body;
        
        if (!groupName || !message) {
            return res.status(400).json({
                error: 'Missing required fields: groupName, message'
            });
        }
        
        // Aplicar delay
        if (delay > 0) {
            await new Promise(resolve => setTimeout(resolve, delay * 1000));
        }
        
        // Buscar grupo pelo nome
        const chats = await client.getChats();
        const group = chats.find(chat => 
            chat.isGroup && 
            chat.name.toLowerCase().includes(groupName.toLowerCase())
        );
        
        if (!group) {
            return res.status(404).json({
                error: 'Group not found',
                groupName: groupName
            });
        }
        
        // Enviar mensagem para o grupo
        const sentMessage = await client.sendMessage(group.id._serialized, message);
        
        res.json({
            success: true,
            message_id: sentMessage.id._serialized,
            group_id: group.id._serialized,
            group_name: group.name,
            timestamp: new Date().toISOString()
        });
        
    } catch (error) {
        console.error('Error sending group message:', error.message);
        res.status(500).json({
            error: 'Failed to send group message',
            details: error.message
        });
    }
});

// Atualizar status
app.post('/update-status', async (req, res) => {
    try {
        if (!isReady) {
            return res.status(503).json({
                error: 'WhatsApp client not ready'
            });
        }
        
        const { message } = req.body;
        
        if (!message) {
            return res.status(400).json({
                error: 'Missing required field: message'
            });
        }
        
        // Enviar status (story)
        await client.sendMessage('status@broadcast', message);
        
        res.json({
            success: true,
            message: 'Status updated successfully',
            timestamp: new Date().toISOString()
        });
        
    } catch (error) {
        console.error('Error updating status:', error.message);
        res.status(500).json({
            error: 'Failed to update status',
            details: error.message
        });
    }
});

// Listar grupos
app.get('/groups', async (req, res) => {
    try {
        if (!isReady) {
            return res.status(503).json({
                error: 'WhatsApp client not ready'
            });
        }
        
        const chats = await client.getChats();
        const groups = chats
            .filter(chat => chat.isGroup)
            .map(group => ({
                id: group.id._serialized,
                name: group.name,
                participants: group.participants ? group.participants.length : 0,
                isReadOnly: group.isReadOnly,
                lastMessage: group.lastMessage ? {
                    body: group.lastMessage.body,
                    timestamp: group.lastMessage.timestamp
                } : null
            }));
        
        res.json({
            groups: groups,
            total: groups.length
        });
        
    } catch (error) {
        console.error('Error listing groups:', error.message);
        res.status(500).json({
            error: 'Failed to list groups',
            details: error.message
        });
    }
});

// Health check
app.get('/health', (req, res) => {
    res.json({
        status: 'healthy',
        whatsapp_ready: isReady,
        uptime: process.uptime(),
        memory: process.memoryUsage(),
        timestamp: new Date().toISOString()
    });
});

// Inicializar WhatsApp Client
console.log('Initializing WhatsApp Client...');
client.initialize();

// Iniciar servidor
app.listen(PORT, '0.0.0.0', () => {
    console.log(`WhatsApp Microservice running on port ${PORT}`);
    console.log(`Django API URL: ${DJANGO_API_URL}`);
});

