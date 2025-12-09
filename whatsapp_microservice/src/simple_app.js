const express = require('express');
const cors = require('cors');
const { Client, LocalAuth } = require('whatsapp-web.js');
const qrcode = require('qrcode');

const app = express();
const PORT = process.env.PORT || 3001;

// Middleware
app.use(cors());
app.use(express.json());

// Estado global
let client = null;
let qrCodeData = null;
let isConnected = false;
let connectionStatus = 'disconnected';

// Inicializar cliente WhatsApp
function initializeWhatsApp() {
    console.log('Inicializando cliente WhatsApp...');
    
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

    // Event listeners
    client.on('qr', async (qr) => {
        console.log('QR Code recebido');
        qrCodeData = qr;
        connectionStatus = 'qr_ready';
        
        try {
            const qrImage = await qrcode.toDataURL(qr);
            console.log('QR Code convertido para base64');
        } catch (err) {
            console.error('Erro ao gerar QR Code:', err);
        }
    });

    client.on('ready', () => {
        console.log('Cliente WhatsApp conectado!');
        isConnected = true;
        connectionStatus = 'connected';
        qrCodeData = null;
    });

    client.on('authenticated', () => {
        console.log('Cliente autenticado');
        connectionStatus = 'authenticated';
    });

    client.on('auth_failure', (msg) => {
        console.error('Falha na autenticação:', msg);
        connectionStatus = 'auth_failed';
    });

    client.on('disconnected', (reason) => {
        console.log('Cliente desconectado:', reason);
        isConnected = false;
        connectionStatus = 'disconnected';
        qrCodeData = null;
    });

    // Inicializar cliente
    client.initialize().catch(err => {
        console.error('Erro ao inicializar cliente:', err);
        connectionStatus = 'error';
    });
}

// Rotas da API
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
            timestamp: new Date().toISOString()
        });
    } catch (error) {
        console.error('Erro ao obter status:', error);
        res.status(500).json({
            error: 'Erro interno do servidor',
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
            timestamp: new Date().toISOString()
        });
    } catch (error) {
        console.error('Erro ao obter status:', error);
        res.status(500).json({
            error: 'Erro interno do servidor',
            status: connectionStatus,
            connected: false
        });
    }
});

app.get('/api/qr', async (req, res) => {
    try {
        if (qrCodeData && connectionStatus === 'qr_ready') {
            const qrImage = await qrcode.toDataURL(qrCodeData);
            res.json({
                qr_code: qrImage,
                status: connectionStatus
            });
        } else {
            res.json({
                qr_code: null,
                status: connectionStatus,
                message: 'QR Code não disponível'
            });
        }
    } catch (error) {
        console.error('Erro ao obter QR Code:', error);
        res.status(500).json({
            error: 'Erro ao gerar QR Code',
            qr_code: null
        });
    }
});

app.post('/api/send-message', async (req, res) => {
    try {
        if (!isConnected) {
            return res.status(400).json({
                error: 'WhatsApp não conectado'
            });
        }

        const { phone, message } = req.body;
        
        if (!phone || !message) {
            return res.status(400).json({
                error: 'Telefone e mensagem são obrigatórios'
            });
        }

        const chatId = phone.includes('@') ? phone : `${phone}@c.us`;
        await client.sendMessage(chatId, message);
        
        res.json({
            success: true,
            message: 'Mensagem enviada com sucesso'
        });
    } catch (error) {
        console.error('Erro ao enviar mensagem:', error);
        res.status(500).json({
            error: 'Erro ao enviar mensagem',
            details: error.message
        });
    }
});

app.post('/api/restart', (req, res) => {
    try {
        if (client) {
            client.destroy();
        }
        
        setTimeout(() => {
            initializeWhatsApp();
        }, 2000);
        
        res.json({
            success: true,
            message: 'Cliente reiniciado'
        });
    } catch (error) {
        console.error('Erro ao reiniciar cliente:', error);
        res.status(500).json({
            error: 'Erro ao reiniciar cliente'
        });
    }
});

// Iniciar servidor
app.listen(PORT, '0.0.0.0', () => {
    console.log(`Microserviço WhatsApp rodando na porta ${PORT}`);
    console.log(`URL da API Django: http://localhost:8000`);
    
    // Inicializar WhatsApp após 2 segundos
    setTimeout(() => {
        initializeWhatsApp();
    }, 2000);
});

// Graceful shutdown
process.on('SIGINT', () => {
    console.log('Encerrando microserviço...');
    if (client) {
        client.destroy();
    }
    process.exit(0);
});

process.on('SIGTERM', () => {
    console.log('Encerrando microserviço...');
    if (client) {
        client.destroy();
    }
    process.exit(0);
});

