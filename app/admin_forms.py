from django import forms
from django.forms import inlineformset_factory

from .models import Category, Product, ProductImage, ProductVariant


class AdminLoginForm(forms.Form):
    username = forms.CharField(
        max_length=150,
        widget=forms.TextInput(attrs={
            "class": "form-control",
            "placeholder": "Username",
            "autocomplete": "username"
        })
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            "class": "form-control",
            "placeholder": "Password",
            "autocomplete": "current-password"
        })
    )


class CategoryForm(forms.ModelForm):
    class Meta:
        model = Category
        fields = ["name", "slug", "is_active", "image"]
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-control", "placeholder": "Category Name"}),
            "slug": forms.TextInput(attrs={"class": "form-control", "placeholder": "category-slug"}),
            "is_active": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "image": forms.FileInput(attrs={"class": "form-control", "accept": "image/*"}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["slug"].required = False
    
    def clean_image(self):
        image = self.cleaned_data.get('image')
        # Only validate if a new image is being uploaded (not an existing file)
        if image and hasattr(image, 'size'):
            # Check file size (5MB = 5 * 1024 * 1024 bytes)
            max_size = 5 * 1024 * 1024  # 5MB in bytes
            if image.size > max_size:
                raise forms.ValidationError(f'Image file size cannot exceed 5MB. Current size: {image.size / (1024 * 1024):.2f}MB')
            
            # Check if it's a valid image file
            try:
                from PIL import Image
                img = Image.open(image)
                img.verify()
                # Reset file pointer after verification
                image.seek(0)
            except Exception:
                raise forms.ValidationError('Invalid image file. Please upload a valid image (JPG, PNG, GIF, WebP).')
        
        return image


class ProductForm(forms.ModelForm):
    class Meta:
        model = Product
        fields = [
            "category",
            "name",
            "slug",
            "description",
            "material",
            "plating_type",
            "finish",
            "occasion",
            "style",
            "care_instructions",
            "price",
            "original_price",
            "is_featured",
            "is_bestseller",
            "is_active",
        ]
        widgets = {
            "category": forms.Select(attrs={"class": "form-control"}),
            "name": forms.TextInput(attrs={"class": "form-control", "placeholder": "Jewelry Name"}),
            "slug": forms.TextInput(attrs={"class": "form-control", "placeholder": "product-slug"}),
            "description": forms.Textarea(attrs={"class": "form-control", "rows": 4, "placeholder": "Detailed product description"}),
            "material": forms.TextInput(attrs={"class": "form-control", "placeholder": "e.g., Brass, Copper, Alloy"}),
            "plating_type": forms.TextInput(attrs={"class": "form-control", "placeholder": "e.g., Gold Plated, Rose Gold Plated"}),
            "finish": forms.TextInput(attrs={"class": "form-control", "placeholder": "e.g., Polished, Matte, Antique"}),
            "occasion": forms.TextInput(attrs={"class": "form-control", "placeholder": "e.g., Daily Wear, Party Wear, Wedding"}),
            "style": forms.TextInput(attrs={"class": "form-control", "placeholder": "e.g., Traditional, Modern, Contemporary"}),
            "care_instructions": forms.Textarea(attrs={"class": "form-control", "rows": 3, "placeholder": "Instructions for jewelry care and maintenance"}),
            "price": forms.NumberInput(attrs={"class": "form-control", "placeholder": "0.00", "step": "0.01"}),
            "original_price": forms.NumberInput(attrs={"class": "form-control", "placeholder": "0.00 (optional)", "step": "0.01"}),
            "is_featured": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "is_bestseller": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "is_active": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["slug"].required = False
        self.fields["original_price"].required = False
        self.fields["material"].required = False
        self.fields["plating_type"].required = False
        self.fields["finish"].required = False
        self.fields["occasion"].required = False
        self.fields["style"].required = False
        self.fields["care_instructions"].required = False


class ProductImageForm(forms.ModelForm):
    class Meta:
        model = ProductImage
        fields = ["image", "is_primary", "alt_text"]
        widgets = {
            "image": forms.FileInput(attrs={"class": "form-control", "accept": "image/*"}),
            "is_primary": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "alt_text": forms.TextInput(attrs={"class": "form-control", "placeholder": "Alt text"}),
        }
    
    def clean_image(self):
        image = self.cleaned_data.get('image')
        # Only validate if a new image is being uploaded (not an existing file)
        if image and hasattr(image, 'size'):
            # Check file size (5MB = 5 * 1024 * 1024 bytes)
            max_size = 5 * 1024 * 1024  # 5MB in bytes
            if image.size > max_size:
                raise forms.ValidationError(f'Image file size cannot exceed 5MB. Current size: {image.size / (1024 * 1024):.2f}MB')
            
            # Check if it's a valid image file
            try:
                from PIL import Image
                img = Image.open(image)
                img.verify()
                # Reset file pointer after verification
                image.seek(0)
            except Exception:
                raise forms.ValidationError('Invalid image file. Please upload a valid image (JPG, PNG, GIF, WebP).')
        
        return image


ProductImageFormSet = inlineformset_factory(
    Product,
    ProductImage,
    form=ProductImageForm,
    extra=3,  # Show 3 empty forms by default
    can_delete=True,
    max_num=5,  # Allow up to 5 images maximum
    validate_max=True,  # Enforce maximum limit
)


class ProductVariantForm(forms.ModelForm):
    class Meta:
        model = ProductVariant
        fields = ["sku", "size_type", "size", "color", "design", "stock_quantity", "is_active"]
        widgets = {
            "sku": forms.TextInput(attrs={"class": "form-control", "placeholder": "SKU"}),
            "size_type": forms.Select(attrs={"class": "form-control"}),
            "size": forms.TextInput(attrs={"class": "form-control", "placeholder": "e.g., 2.4, 7, 18 inches"}),
            "color": forms.TextInput(attrs={"class": "form-control", "placeholder": "Color Tone (e.g., Gold, Rose Gold)"}),
            "design": forms.TextInput(attrs={"class": "form-control", "placeholder": "Design variant (optional)"}),
            "stock_quantity": forms.NumberInput(attrs={"class": "form-control", "placeholder": "0", "min": "0"}),
            "is_active": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }
        help_texts = {
            "size_type": "Select the appropriate size type based on category",
            "size": "Enter size value: 2.4 for bangles, 7 for rings, 18 inches for chains, etc.",
        }


ProductVariantFormSet = inlineformset_factory(
    Product,
    ProductVariant,
    form=ProductVariantForm,
    extra=3,  # Show 3 empty forms by default
    can_delete=True,
    max_num=50,  # Allow up to 50 variants (different sizes/colors)
)

