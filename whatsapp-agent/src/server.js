const express = require('express');
const http = require('http');
const socketIo = require('socket.io');
const cors = require('cors');
const path = require('path');
const { startWhatsAppClient } = require('./whatsapp');

const app = express();
const server = http.createServer(app);
const io = socketIo(server, {
  cors: { origin: 'http://localhost:3000', methods: ['GET', 'POST'] }
});

app.use(cors());
app.use(express.json());
app.use(express.static(path.join(__dirname, '../public')));

app.get('/', (req, res) => {
  res.sendFile(path.join(__dirname, '../public/index.html'));
});

app.post('/api/send-message', async (req, res) => {
  const { to, message } = req.body;
  try {
    const client = global.whatsappClient;
    if (!client) throw new Error('WhatsApp client not initialized');
    await client.sendText(to, message);
    res.status(200).json({ success: true });
  } catch (error) {
    console.error('Error sending message:', error);
    res.status(500).json({ error: 'Failed to send message' });
  }
});

app.get('/api/chats', async (req, res) => {
  try {
    const client = global.whatsappClient;
    if (!client) {
      return res.status(400).json({ error: 'WhatsApp client not initialized' });
    }
    const chats = await client.getAllChats();
    const chatData = [];
    for (const chat of chats) {
      const messages = await client.getMessages(chat.id._serialized, { count: 10 });
      chatData.push({
        id: chat.id._serialized,
        name: chat.name || chat.id.user,
        messages: messages.map((msg) => ({
          id: msg.id._serialized,
          from: msg.from,
          body: msg.body || '',
          timestamp: msg.timestamp,
          isFromMe: msg.fromMe
        }))
      });
    }
    res.status(200).json(chatData);
  } catch (error) {
    console.error('Error fetching chats:', error);
    res.status(500).json({ error: 'Failed to fetch chats' });
  }
});

(async () => {
  try {
    global.whatsappClient = await startWhatsAppClient(io);
    console.log('WhatsApp client initialized');
  } catch (error) {
    console.error('Failed to initialize WhatsApp client:', error);
  }
})();

const PORT = process.env.PORT || 3000;
server.listen(PORT, () => {
  console.log(`Server running on http://localhost:${PORT}`);
});