# Installation and Usage Guide - WhatsApp Sales Agent (v2 - Modular AI Configuration)

This guide contains detailed instructions to set up and run the WhatsApp Sales Agent in your local environment, now with separated AI configuration and improved integration with the Google Gemini API.

## Requirements

- Python 3.8 or higher
- Django 4.2 LTS
- Pillow (for image handling)
- Requests (for API communication)
- Google Generative AI (for Gemini integration)
- SQLite (included with Python)

## Installation

1.  **Extract the zip file**
    ```bash
    unzip whatsapp_agent_refactored.zip -d whatsapp_agent_project
    cd whatsapp_agent_project
    ```
    *(Note: The zip file name will be updated later)*

2.  **Create a virtual environment**
    ```bash
    python -m venv venv
    ```

3.  **Activate the virtual environment**
    - Windows:
      ```bash
      source venv/Scripts/activate
      ```
    - Linux/Mac:
      ```bash
      source venv/bin/activate
      ```

4.  **Install dependencies**
    ```bash
    pip install django==4.2 pillow requests google-generativeai
    ```

5.  **Run migrations**
    ```bash
    python manage.py makemigrations core
    python manage.py migrate
    ```
    *(Note: This will apply new migrations for the AIConfig model)*

6.  **Create a superuser**
    ```bash
    python manage.py createsuperuser
    ```

7.  **Start the server**
    ```bash
    python manage.py runserver
    ```

8.  **Access the system**
    - Admin panel: http://127.0.0.1:8000/admin/
    - Dashboard: http://127.0.0.1:8000/
    - WhatsApp Configuration: http://127.0.0.1:8000/config/
    - **New AI Configuration:** http://127.0.0.1:8000/ai-config/
    - AI Test: http://127.0.0.1:8000/ai-test/

## Google Gemini API Configuration (New Structure)

The Google Gemini API configuration has been separated from WhatsApp configuration for greater modularity and flexibility, especially considering a future SaaS model.

**API Key Priority:**

The system now looks for the Gemini API key in the following order:

1.  **Database (Active AIConfig):** Attempts to find an active instance (`is_active=True`) of the `AIConfig` model in the database and use its `api_key`.
2.  **Settings (Fallback):** If no key is found in the database (no `AIConfig` instance exists, none active, or the key is empty), the system looks for a variable `DEFAULT_GEMINI_API_KEY` in the `whatsapp_agent/settings.py` file.
3.  **Environment Variable (Fallback):** If not found in `settings.py`, it tries to get the environment variable `DEFAULT_GEMINI_API_KEY`.

**How to Configure:**

**Method 1: Configuration via Interface (Recommended)**

1.  **Get a Google Gemini API key:** Visit [https://ai.google.dev/](https://ai.google.dev/) and generate your key.
2.  **Access the New Configuration Page:**
    *   In the dashboard sidebar, click "**AI Configuration**."
    *   You will be directed to `http://127.0.0.1:8000/ai-config/`.
3.  **Set the Key:**
    *   If no configuration exists, the form will be ready to create a new one.
    *   Select the provider (currently only "gemini").
    *   Enter your Google Gemini API key in the "**Api key**" field.
    *   Check "**Is active**" so the system uses this configuration. *Only one AI configuration can be active at a time.*
    *   Click "**Save Configuration**."
    *   The key will be saved in the database. The AI service will automatically reconfigure to use this key.

**Method 2: Default Configuration via `settings.py` (Fallback)**

1.  **Define the Key in the Project:**
    *   Open the `whatsapp_agent/settings.py` file.
    *   Add the following line (or modify if it already exists), replacing `YOUR_DEFAULT_API_KEY` with your key:
        ```python
        DEFAULT_GEMINI_API_KEY = 'YOUR_DEFAULT_API_KEY'
        ```
    *   Save the file.
2.  **How it works:** If no active AI configuration is defined in the database (Method 1), the system uses this key as fallback.

**Checking the Configuration:**

*   On the "AI Configuration" page, the "AI Configured" status will indicate if the AI service successfully initialized (either by the database key or fallback).
*   Go to the "**AI Test**" menu (http://127.0.0.1:8000/ai-test/).
*   Send a test message (e.g., "Recommend an Asus i5 notebook").
*   Check if the AI replies correctly. If no key is configured or the key is invalid, you will receive an error message or fallback response.

**Important:** The `gemini_api_key` field has been **removed** from the "WhatsApp Configuration" page. AI configuration is now exclusively managed on the "AI Configuration" page.

## WhatsApp Integration

### Option 1: Z-API (Recommended for MVP)

1. **Create a Z-API account**
   - Visit [https://www.z-api.io/](https://www.z-api.io/)
   - Register and create an instance
   - Connect your WhatsApp Business by scanning the QR Code

2. **Configure the API in the system**
   - On the dashboard, go to "WhatsApp Configuration"
   - Select "Z-API" as the provider
   - Fill in the Token and Instance ID (available in the Z-API panel)
   - Enter your phone number in international format (e.g., 5511999999999)

3. **Configure the Webhook**
   - In the Z-API panel, go to "Webhooks"
   - Add the webhook URL shown on the system configuration page
   - For local testing, use ngrok to expose your local server (see below)

### Option 2: 360dialog

1. **Create a 360dialog account**
   - Visit [https://www.360dialog.com/](https://www.360dialog.com/)
   - Follow the registration and verification process

2. **Configure the API in the system**
   - On the dashboard, go to "WhatsApp Configuration"
   - Select "360dialog" as the provider
   - Fill in the credentials provided by 360dialog

## Exposing Your Local Server with ngrok (for testing)

To receive webhooks in your local environment, you need to expose your server:

1. **Install ngrok**
   - Download from [https://ngrok.com/download](https://ngrok.com/download)
   - Follow installation instructions

2. **Expose your local server**
