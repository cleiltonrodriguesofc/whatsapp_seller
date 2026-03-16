# 🚀 WhatsApp Automation Kit (Evolution API + GitHub Actions)

Instructions to implement this WhatsApp automation in your new project.

## 1. Setup Instructions

1.  **Copy Files**:
    - Copy `infrastructure/whatsapp.py` to your infrastructure layer.
    - Copy `use_cases/notifications.py` to your application layer.
    - Copy `api/views_example.py` to your views/interfaces layer.
    - Copy `workflow/automation.yml` to `.github/workflows/`.

2.  **Environment Variables**:
    - Add the variables from `.env.example` to your `.env` and your production server (e.g., Render/Heroku).
    - **Note**: Since you are using the same WhatsApp number, use the **same** `EVOLUTION_API_URL`, `EVOLUTION_API_KEY`, and `EVOLUTION_INSTANCE` from the previous project.

3.  **GitHub Secrets**:
    - Add the `TRIGGER_TOKEN` to your new repository's **Settings -> Secrets and variables -> Actions**.

## 2. Instructions for the AI Assistant

Tell the AI:
> "I want to implement WhatsApp automation. I've already provided a kit in the `whatsapp_automation_kit` folder. 
> 
> 1. Use the `EvolutionWhatsAppService` for communication.
> 2. Implement a use case to send sales campaigns to groups.
> 3. Use the `whatsapp_webhook_trigger` pattern in my views to allow GitHub Actions to trigger it.
> 4. Help me find the Group JIDs using the `get_groups()` method in the service."

## 3. Key Differences for Sales Agent project
- **Targeting**: In your new project, you can pass different `jid` parameters to the webhook to target different groups dynamically.
- **Content**: Customize the `SalesAgentCampaignUseCase` to include product links and images.
