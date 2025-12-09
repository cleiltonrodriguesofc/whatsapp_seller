// Add at the top of script.js
window.onload = () => {
  const qrContainer = document.getElementById('qr-code');
  new QRCode(qrContainer, {
    text: 'test-qr-code',
    width: 150,
    height: 150
  });
};


const socket = io('http://localhost:3000');

socket.on('qr', (qr) => {
  console.log('QR code received:', qr); // Debug log
  document.getElementById('status').textContent = 'Status: Scan QR Code';
  const qrContainer = document.getElementById('qr-code');
  qrContainer.innerHTML = '';
  new QRCode(qrContainer, {
    text: qr,
    width: 150,
    height: 150
  });
});

socket.on('ready', async (msg) => {
  console.log('Client ready:', msg); // Debug log
  document.getElementById('status').textContent = `Status: ${msg}`;
  document.getElementById('qr-code').innerHTML = '';
  await loadChats();
});

socket.on('message', (msg) => {
  console.log('Message received:', msg); // Debug log
  const chatList = document.getElementById('chat-list');
  const li = document.createElement('li');
  li.textContent = `${msg.from}: ${msg.body || ''}`;
  chatList.appendChild(li);
  chatList.scrollTop = chatList.scrollHeight;
});

async function loadChats() {
  try {
    const response = await fetch('/api/chats');
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const chats = await response.json();
    const chatList = document.getElementById('chat-list');
    chatList.innerHTML = '';
    chats.forEach((chat) => {
      const li = document.createElement('li');
      li.innerHTML = `<strong>${chat.name}</strong><br>${chat.messages
        .map(
          (msg) =>
            `${
              msg.isFromMe ? 'You' : msg.from
            }: ${msg.body} <small>(${new Date(
              msg.timestamp * 1000
            ).toLocaleString()})</small>`
        )
        .join('<br>')}`;
      chatList.appendChild(li);
    });
    chatList.scrollTop = chatList.scrollHeight;
  } catch (error) {
    console.error('Error loading chats:', error);
  }
}

async function sendMessage() {
  const recipient = document.getElementById('recipient').value;
  const message = document.getElementById('message').value;
  if (!recipient || !message) {
    alert('Please enter recipient and message');
    return;
  }
  try {
    const response = await fetch('/api/send-message', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ to: recipient, message })
    });
    const result = await response.json();
    if (result.success) {
      document.getElementById('message').value = '';
      await loadChats();
    } else {
      alert('Failed to send message');
    }
  } catch (error) {
    console.error('Error sending message:', error);
    alert('Error sending message');
  }
}