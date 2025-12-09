const wppconnect = require('@wppconnect-team/wppconnect');

async function startWhatsAppClient(io) {
  try {
    const client = await wppconnect.create({
      session: 'whatsapp-session',
      puppeteerOptions: {
        headless: true,
        args: [
          '--no-sandbox',
          '--disable-setuid-sandbox',
          '--disable-gpu',
          '--disable-dev-shm-usage',
          '--disable-accelerated-2d-canvas',
          '--no-first-run',
          '--no-zygote',
          '--single-process'
        ],
        executablePath: undefined,
        userDataDir: './tokens'
      },
      webVersion: '2.2412.54',
      autoClose: false,
      logQR: false,
      disableUpdateCheck: true
    });

    client.on('qr', (qr) => {
      console.log('QR Code emitted:', qr); // Debug QR code content
      io.emit('qr', qr);
    });

    client.on('ready', () => {
      console.log('WhatsApp Client is ready!');
      io.emit('ready', 'Client is ready!');
    });

    client.on('message_create', async (message) => {
      console.log(`Message from ${message.from}: ${message.body}`);
      io.emit('message', message);
      if (message.body.toLowerCase() === 'hello') {
        await client.sendText(message.from, 'Hi! How can I assist you?');
      }
    });

    return client;
  } catch (error) {
    console.error('Error starting WhatsApp client:', error);
    throw error;
  }
}

module.exports = { startWhatsAppClient };