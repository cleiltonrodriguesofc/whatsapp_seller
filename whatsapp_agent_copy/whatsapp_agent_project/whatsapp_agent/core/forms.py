"""
forms for the core app.
"""
from django import forms
from .models import Product, Contact, Group, WhatsAppConfig, StatusUpdate, AIConfig


class ProductForm(forms.ModelForm):
    """form for product model"""
    class Meta:
        model = Product
        fields = ['name', 'description', 'price', 'image', 'category', 'affiliate_link', 'is_active']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 4}),
            'price': forms.NumberInput(attrs={'step': '0.01'}),
        }


class ContactForm(forms.ModelForm):
    """form for contact model"""
    persona_prompt = forms.CharField(
        widget=forms.Textarea(attrs={'rows': 4}), 
        required=False, 
        help_text="Define como a IA deve se comportar especificamente com este contato. Se preenchido, sobrescreve a persona geral da IA."
    )
    
    class Meta:
        model = Contact
        fields = ['phone_number', 'name', 'is_allowed', 'persona_prompt']


class GroupForm(forms.ModelForm):
    """form for group model"""
    class Meta:
        model = Group
        fields = ['group_id', 'name', 'is_allowed']


class WhatsAppConfigForm(forms.ModelForm):
    """form for whatsapp configuration"""
    # Explicitly define fields to ensure they are optional
    provider = forms.ChoiceField(choices=WhatsAppConfig.PROVIDER_CHOICES, required=False)
    token = forms.CharField(max_length=255, required=False, widget=forms.PasswordInput(render_value=True))
    instance = forms.CharField(max_length=255, required=False)
    phone_number = forms.CharField(max_length=20, required=False)
    gemini_api_key = forms.CharField(max_length=255, required=False, help_text="Your Google Gemini API Key", widget=forms.TextInput(attrs={"placeholder": "Enter your Google Gemini API Key"}))
    # is_active is handled by default BooleanField behavior (checkbox)

    class Meta:
        model = WhatsAppConfig
        # Ensure all fields are listed, including the explicitly defined ones
        fields = ["provider", "token", "instance", "phone_number", "gemini_api_key", "is_active"]
        # Widgets for explicitly defined fields are set above
        widgets = {
            # Only include widgets for fields NOT explicitly defined above, if needed
            # 'is_active': forms.CheckboxInput() # Default is fine
        }


class StatusUpdateForm(forms.ModelForm):
    """form for status updates"""
    class Meta:
        model = StatusUpdate
        fields = ['title', 'content', 'image', 'products', 'scheduled_for']
        widgets = {
            'content': forms.Textarea(attrs={'rows': 4}),
            'scheduled_for': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
            'products': forms.SelectMultiple(attrs={'size': 5}),
        }


class BulkMessageForm(forms.Form):
    """form for sending bulk messages"""
    message = forms.CharField(widget=forms.Textarea(attrs={'rows': 4}))
    include_image = forms.BooleanField(required=False)
    image = forms.ImageField(required=False)
    send_to_contacts = forms.BooleanField(required=False)
    send_to_groups = forms.BooleanField(required=False)
    contacts = forms.ModelMultipleChoiceField(
        queryset=Contact.objects.filter(is_allowed=True),
        required=False,
        widget=forms.SelectMultiple(attrs={'size': 5})
    )
    groups = forms.ModelMultipleChoiceField(
        queryset=Group.objects.filter(is_allowed=True),
        required=False,
        widget=forms.SelectMultiple(attrs={'size': 5})
    )


class SearchForm(forms.Form):
    """form for searching products"""
    query = forms.CharField(max_length=100, required=False)
    category = forms.ChoiceField(choices=[], required=False)
    
    def __init__(self, *args, **kwargs):
        super(SearchForm, self).__init__(*args, **kwargs)
        # dynamically get categories from products
        from .models import Product
        categories = Product.objects.values_list('category', flat=True).distinct()
        category_choices = [('', 'All Categories')] + [(c, c) for c in categories]
        self.fields['category'].choices = category_choices



class AIConfigForm(forms.ModelForm):
    """form for ai configuration"""
    api_key = forms.CharField(max_length=255, required=False, widget=forms.PasswordInput(render_value=True), help_text="API Key for the selected provider")
    persona_prompt = forms.CharField(widget=forms.Textarea(attrs={'rows': 4}), required=False, help_text="Define the AI's persona or system prompt (e.g., 'You are a helpful clothing sales assistant specializing in summer wear.')")

    class Meta:
        model = AIConfig
        fields = ["provider", "api_key", "persona_prompt", "is_active"]
        # Add widgets if needed, e.g., for provider if more options exist
        widgets = {
            # Example: customize provider dropdown if needed
            # 'provider': forms.Select(attrs={'class': 'form-control'}),
        }
