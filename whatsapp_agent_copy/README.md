# WhatsApp Sales Agent - Complete Solution

A comprehensive WhatsApp automation platform built with Django and Node.js that provides real WhatsApp Web functionality, AI-powered conversations, and advanced sales management features.

## 🚀 Features

### 📱 WhatsApp Integration
- **Real WhatsApp Web Interface** - Exact replica of WhatsApp Web within your Django app
- **QR Code Authentication** - Connect your WhatsApp account by scanning QR code
- **Live Conversations** - View and manage your actual WhatsApp conversations
- **Message Management** - Send and receive messages in real-time
- **Contact Management** - Access your WhatsApp contacts
- **Group Support** - Handle WhatsApp groups and broadcast lists

### 🤖 AI-Powered Features
- **Contextual AI Responses** - Intelligent responses based on conversation history
- **Dynamic Personalization** - AI adapts to each contact's communication style
- **Proactive Messaging** - Automated follow-ups based on customer behavior
- **Sentiment Analysis** - Understand customer emotions and respond appropriately
- **Multi-Model Support** - OpenAI GPT, Google Gemini, and open-source alternatives

### 💼 Sales Management
- **Lead Tracking** - Comprehensive lead management system
- **Sales Pipeline** - Track deals from prospect to close
- **Product Catalog** - Manage products with images and descriptions
- **Bulk Messaging** - Send targeted messages to groups or contacts
- **Campaign Management** - Create and track marketing campaigns
- **Analytics Dashboard** - Detailed insights and performance metrics

### ⚡ Advanced Automation
- **Command System** - Control the system via WhatsApp commands
- **Scheduled Messages** - Time-based message automation
- **Auto-Responses** - Intelligent automatic replies
- **Workflow Automation** - Custom business process automation
- **Integration APIs** - Connect with external systems

## 🏗️ Architecture

### Backend Components
- **Django Application** - Main web application and API
- **Node.js Microservice** - WhatsApp Web integration using whatsapp-web.js
- **SQLite Database** - Data storage (easily upgradeable to PostgreSQL)
- **RESTful APIs** - Communication between components

### Frontend Components
- **WhatsApp Web Interface** - Pixel-perfect WhatsApp Web replica
- **Admin Dashboard** - Comprehensive management interface
- **Responsive Design** - Works on desktop and mobile devices
- **Real-time Updates** - Live status and message updates

## 📋 Requirements

### System Requirements
- **Python 3.8+**
- **Node.js 16+**
- **Chrome/Chromium** (for WhatsApp Web automation)
- **4GB RAM minimum** (8GB recommended)
- **Linux/macOS/Windows**

### Python Dependencies
```
Django==5.1.3
requests==2.31.0
python-dotenv==1.0.0
Pillow==10.0.0
google-generativeai==0.3.0
openai==1.3.0
```

### Node.js Dependencies
```
whatsapp-web.js==1.23.0
express==4.18.2
cors==2.8.5
qrcode==1.5.3
axios==1.6.0
```

## 🚀 Installation

### 1. Clone the Repository
```bash
git clone <repository-url>
cd whatsapp-sales-agent
```

### 2. Setup Python Environment
```bash
# Create virtual environment
python -m venv venv

# Activate virtual environment
# On Linux/macOS:
source venv/bin/activate
# On Windows:
venv\Scripts\activate

# Install Python dependencies
cd whatsapp_agent_project
pip install -r requirements.txt
```

### 3. Setup Node.js Microservice
```bash
# Navigate to microservice directory
cd ../whatsapp_microservice

# Install Node.js dependencies
npm install
```

### 4. Database Setup
```bash
# Navigate back to Django project
cd ../whatsapp_agent_project

# Run migrations
python manage.py migrate

# Create superuser (optional)
python manage.py createsuperuser
```

### 5. Environment Configuration
Create a `.env` file in the Django project root:
```env
# AI Configuration
OPENAI_API_KEY=your_openai_api_key_here
GEMINI_API_KEY=your_gemini_api_key_here

# Django Settings
SECRET_KEY=your_secret_key_here
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1

# Microservice Configuration
MICROSERVICE_URL=http://localhost:3001
```

## 🎯 Usage

### Starting the Services

#### 1. Start the WhatsApp Microservice
```bash
cd whatsapp_microservice
npm start
```
The microservice will start on `http://localhost:3001`

#### 2. Start the Django Application
```bash
cd whatsapp_agent_project
python manage.py runserver
```
The web application will start on `http://localhost:8000`

### Connecting WhatsApp

#### Method 1: Direct QR Code Connection
1. Visit `http://localhost:8000/whatsapp/connect/`
2. Scan the QR code with your WhatsApp mobile app
3. Go to WhatsApp Settings → Linked Devices → Link a Device
4. Scan the displayed QR code
5. Your WhatsApp will be connected automatically

#### Method 2: Setup Page
1. Visit `http://localhost:8000/whatsapp/setup/`
2. Fill in your phone number and preferences
3. Click "Connect WhatsApp"
4. Scan the generated QR code

### Using WhatsApp Web Interface

1. **Access the Interface**: Visit `http://localhost:8000/whatsapp/web/`
2. **View Conversations**: See all your WhatsApp conversations in real-time
3. **Send Messages**: Click on any conversation to send messages
4. **Search Contacts**: Use the search bar to find specific conversations
5. **Real-time Updates**: Messages update automatically

### AI Configuration

1. **Access AI Settings**: Visit `http://localhost:8000/ai-config/`
2. **Configure AI Model**: Choose between OpenAI GPT or Google Gemini
3. **Set Personality**: Define how the AI should respond to customers
4. **Enable Features**: Turn on contextual responses, proactive messaging, etc.

### Managing Contacts and Sales

1. **Dashboard**: `http://localhost:8000/` - Overview of all activities
2. **Contacts**: `http://localhost:8000/contacts/` - Manage customer contacts
3. **Products**: `http://localhost:8000/products/` - Product catalog management
4. **Sales**: `http://localhost:8000/sales/` - Track sales and deals
5. **Conversations**: `http://localhost:8000/conversations/` - Message history

## 🔧 API Endpoints

### WhatsApp Web APIs
- `GET /api/whatsapp/status/` - Connection status
- `GET /api/whatsapp/conversations/` - List conversations
- `GET /api/whatsapp/conversations/{id}/messages/` - Get chat messages
- `GET /api/whatsapp/contacts/` - List contacts
- `POST /api/whatsapp/send-message/` - Send message

### Sales Management APIs
- `GET /api/products/` - List products
- `GET /api/conversations/` - List conversations
- `POST /api/bulk-message/` - Send bulk messages

### AI Integration APIs
- `POST /api/ai/generate-response/` - Generate AI response
- `GET /api/ai/config/` - Get AI configuration
- `POST /api/ai/config/` - Update AI configuration

## 🛡️ Security Features

### WhatsApp Security
- **Session Management** - Secure WhatsApp session handling
- **Rate Limiting** - Prevents spam and account bans
- **Message Intervals** - Configurable delays between messages
- **Auto-disconnect** - Automatic disconnection on suspicious activity

### Application Security
- **CSRF Protection** - Django CSRF middleware enabled
- **SQL Injection Prevention** - Django ORM protection
- **XSS Protection** - Template auto-escaping
- **Secure Headers** - Security middleware configured

## 📊 Monitoring and Analytics

### Real-time Monitoring
- **Connection Status** - Live WhatsApp connection monitoring
- **Message Delivery** - Track message delivery status
- **Error Logging** - Comprehensive error tracking
- **Performance Metrics** - Response time monitoring

### Analytics Dashboard
- **Conversation Analytics** - Message volume and response times
- **Sales Metrics** - Conversion rates and revenue tracking
- **AI Performance** - Response accuracy and customer satisfaction
- **Campaign Results** - Marketing campaign effectiveness

## 🔄 Deployment

### Development Deployment
```bash
# Start microservice
cd whatsapp_microservice && npm start

# Start Django (in another terminal)
cd whatsapp_agent_project && python manage.py runserver
```

### Production Deployment

#### Using Docker (Recommended)
```bash
# Build and run with Docker Compose
docker-compose up -d
```

#### Manual Production Setup
```bash
# Install production dependencies
pip install gunicorn
npm install -g pm2

# Start microservice with PM2
cd whatsapp_microservice
pm2 start npm --name "whatsapp-microservice" -- start

# Start Django with Gunicorn
cd whatsapp_agent_project
gunicorn whatsapp_agent.wsgi:application --bind 0.0.0.0:8000
```

#### Environment Variables for Production
```env
DEBUG=False
ALLOWED_HOSTS=yourdomain.com,www.yourdomain.com
DATABASE_URL=postgresql://user:password@localhost/dbname
MICROSERVICE_URL=http://localhost:3001
```

## 🧪 Testing

### Running Tests
```bash
# Django tests
cd whatsapp_agent_project
python manage.py test

# Node.js tests
cd whatsapp_microservice
npm test
```

### Manual Testing Checklist
- [ ] WhatsApp QR code generation
- [ ] WhatsApp connection establishment
- [ ] Message sending and receiving
- [ ] Conversation loading
- [ ] AI response generation
- [ ] Bulk message functionality
- [ ] Dashboard analytics

## 🐛 Troubleshooting

### Common Issues

#### WhatsApp Connection Issues
```bash
# Check microservice status
curl http://localhost:3001/status

# Restart microservice
cd whatsapp_microservice
npm restart

# Clear WhatsApp session
rm -rf .wwebjs_auth/
```

#### Django Issues
```bash
# Check Django logs
python manage.py runserver --verbosity=2

# Reset database
python manage.py flush
python manage.py migrate
```

#### Port Conflicts
```bash
# Check port usage
netstat -tlnp | grep :3001
netstat -tlnp | grep :8000

# Kill processes if needed
kill <process_id>
```

### Error Codes
- **E001**: WhatsApp connection timeout
- **E002**: Invalid QR code
- **E003**: Message sending failed
- **E004**: AI service unavailable
- **E005**: Database connection error

## 📚 Advanced Configuration

### AI Model Configuration
```python
# In settings.py
AI_CONFIG = {
    'model': 'gpt-4',  # or 'gemini-pro'
    'temperature': 0.7,
    'max_tokens': 1000,
    'personality': 'friendly_sales_assistant'
}
```

### WhatsApp Automation Rules
```python
# Anti-ban protection settings
WHATSAPP_CONFIG = {
    'message_interval': 2,  # seconds between messages
    'daily_message_limit': 1000,
    'operating_hours': (7, 23),  # 7 AM to 11 PM
    'weekend_mode': False
}
```

### Custom Commands
```python
# Add custom WhatsApp commands
CUSTOM_COMMANDS = {
    '!help': 'show_help_menu',
    '!status': 'show_order_status',
    '!catalog': 'show_product_catalog',
    '!support': 'transfer_to_human'
}
```

## 🤝 Contributing

### Development Setup
1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests for new features
5. Submit a pull request

### Code Style
- **Python**: Follow PEP 8
- **JavaScript**: Use ESLint configuration
- **HTML/CSS**: Follow BEM methodology
- **Documentation**: Update README for new features

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🆘 Support

### Documentation
- **API Documentation**: `/api/docs/`
- **Admin Guide**: `/admin/`
- **User Manual**: Available in the dashboard

### Community
- **Issues**: Report bugs on GitHub Issues
- **Discussions**: Join GitHub Discussions
- **Email**: support@whatsapp-sales-agent.com

### Professional Support
For enterprise support, custom development, or consulting services, contact our team.

## 🔮 Roadmap

### Upcoming Features
- [ ] Multi-language support
- [ ] Advanced analytics dashboard
- [ ] CRM integrations (Salesforce, HubSpot)
- [ ] Voice message support
- [ ] Video call integration
- [ ] Mobile app companion
- [ ] Webhook integrations
- [ ] Advanced AI training

### Version History
- **v4.0** - WhatsApp Web interface, enhanced AI
- **v3.0** - Microservice architecture, real WhatsApp integration
- **v2.0** - AI contextual responses, proactive messaging
- **v1.0** - Basic WhatsApp automation, sales management

---

**Built with ❤️ for sales teams who want to leverage WhatsApp for business growth.**

