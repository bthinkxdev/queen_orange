from django import forms

from .models import ContactMessage, NewsletterSubscription


class CartAddForm(forms.Form):
    product_id = forms.IntegerField(min_value=1)
    size = forms.CharField(max_length=20)
    color = forms.CharField(max_length=30, required=False)
    quantity = forms.IntegerField(min_value=1)


class CartUpdateForm(forms.Form):
    item_id = forms.IntegerField(min_value=1)
    quantity = forms.IntegerField(min_value=0)


class CheckoutForm(forms.Form):
    full_name = forms.CharField(max_length=120)
    email = forms.EmailField(required=False)
    phone = forms.CharField(max_length=20)
    address = forms.CharField(widget=forms.Textarea)
    city = forms.CharField(max_length=80)
    state = forms.CharField(max_length=80)
    pincode = forms.CharField(max_length=10)
    payment = forms.ChoiceField(
        choices=[("cod", "Cash on Delivery"), ("whatsapp", "WhatsApp Order")],
        widget=forms.RadioSelect,
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["payment"].initial = "cod"
        for field in self.fields.values():
            if isinstance(field.widget, forms.RadioSelect):
                continue
            existing = field.widget.attrs.get("class", "")
            field.widget.attrs["class"] = f"{existing} form-input".strip()


class ContactForm(forms.ModelForm):
    class Meta:
        model = ContactMessage
        fields = ["name", "email", "subject", "message"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            existing = field.widget.attrs.get("class", "")
            field.widget.attrs["class"] = f"{existing} form-input".strip()


class NewsletterForm(forms.ModelForm):
    class Meta:
        model = NewsletterSubscription
        fields = ["email"]

