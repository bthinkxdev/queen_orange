import logging
import time

from django import forms
from django.conf import settings
from django.forms import inlineformset_factory
from django.forms.formsets import DELETION_FIELD_NAME
from django.forms.models import BaseInlineFormSet

from .models import (
    Banner,
    Category,
    ColorVariant,
    ColorVariantImage,
    JewelleryDetail,
    JewelleryImage,
    Product,
    ProductVariant,
    SizeVariant,
)

logger = logging.getLogger(__name__)

# Standard apparel sizes (from size chart) for dropdown
STANDARD_SIZES = [
    "Free Size","XS", "S", "M", "L", "XL",
    "2XL", "3XL", "4XL", "5XL", "6XL",
    "7XL", "8XL", "9XL", "10XL","Age 6M - 12M",
    "Age 1Y - 2Y", "Age 2Y - 3Y", "Age 3Y - 4Y", "Age 4Y - 5Y", "Age 5Y - 6Y", "Age 6Y - 7Y", "Age 7Y - 8Y", "Age 8Y - 9Y", "Age 9Y - 10Y", "Age 10Y - 11Y", "Age 11Y - 12Y"
]


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
        if image and hasattr(image, 'size'):
            # Check file size (5MB = 5 * 1024 * 1024 bytes)
            max_size = 5 * 1024 * 1024  # 5MB in bytes
            if image.size > max_size:
                raise forms.ValidationError(f'Image file size cannot exceed 5MB. Current size: {image.size / (1024 * 1024):.2f}MB')
            
            # Check pixel count (5MP)
            try:
                from PIL import Image
                img = Image.open(image)
                width, height = img.size
                if width * height > 5_000_000:
                    raise forms.ValidationError(
                        f'Image resolution cannot exceed 5 megapixels (5,000,000 pixels).\n'
                        f'Selected image: {getattr(image, "name", "uploaded file")}\n'
                        f'Resolution: {width} x {height} = {width * height:,} pixels.\n'
                        'Please choose a smaller image or resize/compress it before uploading.'
                    )
                img.verify()
                # Reset file pointer after verification
                image.seek(0)
            except forms.ValidationError:
                raise
            except Exception:
                raise forms.ValidationError('Invalid image file. Please upload a valid image (JPG, PNG, GIF, WebP).')
        
        return image


def _validate_banner_image(image, required=True):
    """Validate banner image file size and format. Used by BannerForm."""
    if not image and not required:
        return image
    if not image and required:
        raise forms.ValidationError("Banner image is required.")
    if image and hasattr(image, "size"):
        max_size = 5 * 1024 * 1024
        if image.size > max_size:
            raise forms.ValidationError(
                f"Image file size cannot exceed 5MB. Current size: {image.size / (1024 * 1024):.2f}MB"
            )
        try:
            from PIL import Image as PILImage
            img = PILImage.open(image)
            width, height = img.size
            if width * height > 5_000_000:
                raise forms.ValidationError(
                    "Image resolution cannot exceed 5 megapixels. Please resize or compress."
                )
            img.verify()
            image.seek(0)
        except forms.ValidationError:
            raise
        except Exception:
            raise forms.ValidationError(
                "Invalid image file. Please upload a valid image (JPG, PNG, GIF, WebP)."
            )
    return image


class BannerForm(forms.ModelForm):
    class Meta:
        model = Banner
        fields = ["title", "subtitle", "image", "redirect_url", "is_active", "display_order"]
        widgets = {
            "title": forms.TextInput(attrs={"class": "form-control", "placeholder": "Banner title (optional)"}),
            "subtitle": forms.TextInput(attrs={"class": "form-control", "placeholder": "Banner subtitle (optional)"}),
            "image": forms.FileInput(attrs={"class": "form-control", "accept": "image/*"}),
            "redirect_url": forms.URLInput(attrs={"class": "form-control", "placeholder": "https://... (optional)"}),
            "is_active": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "display_order": forms.NumberInput(attrs={"class": "form-control", "min": 0, "placeholder": "0"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["title"].required = False
        self.fields["subtitle"].required = False
        self.fields["redirect_url"].required = False
        if self.instance and self.instance.pk and self.instance.image:
            self.fields["image"].required = False

    def clean_image(self):
        image = self.cleaned_data.get("image")
        required = not (self.instance and self.instance.pk and getattr(self.instance, "image", None))
        return _validate_banner_image(image, required=required)

    def clean_redirect_url(self):
        url = self.cleaned_data.get("redirect_url")
        if url is not None and str(url).strip() == "":
            return None
        return url


class JewelleryDetailForm(forms.ModelForm):
    class Meta:
        model = JewelleryDetail
        fields = [
            "metal_type",
            "purity",
            "weight",
            "gemstone",
            "making_charge",
            "is_adjustable",
            "stock_quantity",
        ]
        widgets = {
            "metal_type": forms.TextInput(attrs={"class": "form-control", "placeholder": "e.g. Gold, Silver"}),
            "purity": forms.TextInput(attrs={"class": "form-control", "placeholder": "e.g. 18K, 22K, 92.5%"}),
            "weight": forms.NumberInput(attrs={"class": "form-control", "step": "0.001", "placeholder": "grams"}),
            "gemstone": forms.TextInput(attrs={"class": "form-control", "placeholder": "Optional"}),
            "making_charge": forms.NumberInput(attrs={"class": "form-control", "step": "0.01", "min": "0"}),
            "is_adjustable": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "stock_quantity": forms.NumberInput(attrs={"class": "form-control", "min": "0"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["gemstone"].required = False
        self.fields["purity"].required = False
        self.fields["weight"].required = False
        self.fields["making_charge"].required = False

    def clean_weight(self):
        val = self.cleaned_data.get("weight")
        if val in (None, ""):
            return None
        return val

    def clean_making_charge(self):
        val = self.cleaned_data.get("making_charge")
        if val in (None, ""):
            return None
        return val


class JewelleryImageForm(forms.ModelForm):
    """Only updates image field when a new file is uploaded (avoids unnecessary S3 re-upload)."""
    class Meta:
        model = JewelleryImage
        fields = ["image", "is_primary", "display_order"]
        widgets = {
            "image": forms.FileInput(attrs={"class": "form-control", "accept": "image/*"}),
            "is_primary": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "display_order": forms.NumberInput(attrs={"class": "form-control", "min": 0}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["display_order"].required = False

    def clean_image(self):
        # Image optional per form so formset can have empty slots (user adds 0–3 images)
        return _validate_image_file(self.cleaned_data.get("image"), required=False)

    def clean_display_order(self):
        val = self.cleaned_data.get("display_order")
        if val in (None, ""):
            return 0
        return val

    def save(self, commit=True):
        if getattr(settings, "DEBUG_TRACE", False):
            print("[EDIT %.4fs] TRACE: entering JewelleryImageForm.save pk=%s" % (time.perf_counter(), getattr(self.instance, "pk", None)))
            print("[EDIT %.4fs] TRACE image changed: %s" % (time.perf_counter(), bool(self.cleaned_data.get("image"))))
        instance = super().save(commit=False)
        # Only update image field if a new file was uploaded (prevents S3 re-upload of unchanged)
        if not self.cleaned_data.get("image") and instance.pk and getattr(self.instance, "image", None):
            instance.image = self.instance.image
        if commit:
            if getattr(settings, "DEBUG_TRACE", False):
                print("[EDIT %.4fs] TRACE: JewelleryImage save() commit pk=%s" % (time.perf_counter(), instance.pk or "new"))
            logger.debug("Saving image instance %s (JewelleryImage)", instance.pk or "new")
            instance.save()
            if hasattr(self, "_save_m2m"):
                self._save_m2m()
        return instance


class SafeDeleteInlineFormSet(BaseInlineFormSet):
    """Base formset that safely handles forms without cleaned_data (empty extra forms).
    Use for all formsets with can_delete=True to avoid AttributeError in _should_delete_form."""

    def _should_delete_form(self, form):
        cleaned = getattr(form, "cleaned_data", None)
        if cleaned is None:
            return False
        return cleaned.get(DELETION_FIELD_NAME, False)


JewelleryImageFormSet = inlineformset_factory(
    JewelleryDetail,
    JewelleryImage,
    form=JewelleryImageForm,
    formset=SafeDeleteInlineFormSet,
    extra=3,
    can_delete=True,
    max_num=3,
)
# Edit: no extra empty image rows; "Add image" adds a row via JS to keep request size small
JewelleryImageFormSetEdit = inlineformset_factory(
    JewelleryDetail,
    JewelleryImage,
    form=JewelleryImageForm,
    formset=SafeDeleteInlineFormSet,
    extra=0,
    can_delete=True,
    max_num=3,
)


class ProductForm(forms.ModelForm):
    class Meta:
        model = Product
        fields = [
            "product_type",
            "category",
            "name",
            "slug",
            "description",
            "price",
            "original_price",
            "material",
            "is_featured",
            "is_bestseller",
            "is_deal_of_day",
            "deal_of_day_start",
            "deal_of_day_end",
            "is_active",
        ]
        widgets = {
            "product_type": forms.Select(attrs={"class": "form-control", "id": "id_product_type"}),
            "category": forms.Select(attrs={"class": "form-control"}),
            "name": forms.TextInput(attrs={"class": "form-control", "placeholder": "Product Name"}),
            "slug": forms.TextInput(attrs={"class": "form-control", "placeholder": "product-slug"}),
            "description": forms.Textarea(attrs={"class": "form-control", "rows": 4, "placeholder": "Product Description"}),
            "price": forms.NumberInput(attrs={"class": "form-control", "placeholder": "0.00", "step": "0.01"}),
            "original_price": forms.NumberInput(attrs={"class": "form-control", "placeholder": "0.00 (optional)", "step": "0.01"}),
            "material": forms.TextInput(attrs={"class": "form-control", "placeholder": "Material (e.g. Cotton, Brass)"}),
            "is_featured": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "is_bestseller": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "is_deal_of_day": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "deal_of_day_start": forms.DateInput(attrs={"class": "form-control", "type": "date"}),
            "deal_of_day_end": forms.DateInput(attrs={"class": "form-control", "type": "date"}),
            "is_active": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["slug"].required = False
        self.fields["original_price"].required = False
        self.fields["description"].required = False
        self.fields["material"].required = False
        self.fields["deal_of_day_start"].required = False
        self.fields["deal_of_day_end"].required = False
        
        # Filter categories to only show active ones
        active_categories = Category.objects.filter(is_active=True)
        
        # If editing an existing product, include its current category even if inactive
        if self.instance and self.instance.pk:
            current_category = self.instance.category
            if current_category and not current_category.is_active:
                active_categories = active_categories | Category.objects.filter(pk=current_category.pk)
        
        self.fields["category"].queryset = active_categories.order_by('name')
        
        for field_name, field in self.fields.items():
            if field.required and hasattr(field.widget, 'attrs'):
                field.widget.attrs['required'] = 'required'
    
    def clean(self):
        if getattr(settings, "DEBUG_TRACE", False):
            print("[EDIT %.4fs] TRACE: entering ProductForm.clean" % time.perf_counter())
        cleaned_data = super().clean()
        price = cleaned_data.get('price')
        original_price = cleaned_data.get('original_price')
        
        # If original_price is set, price must also be set
        if original_price and not price:
            raise forms.ValidationError(
                "Selling price is required when original price is set."
            )
        
        # If both are set, original_price must be greater than price
        if original_price and price:
            if original_price <= price:
                raise forms.ValidationError(
                    "Original price must be greater than the selling price."
                )

        return cleaned_data


# --- Product EDIT (modular AJAX): basic fields only, no multipart ---
BASIC_EDIT_FIELDS = [
    "name", "slug", "description", "price", "original_price",
    "material", "is_featured", "is_bestseller", "is_active", "category", "product_type",
]


class ProductBasicEditForm(forms.ModelForm):
    """Simple form for POST /admin/products/<id>/update-basic/. No images, no variants."""
    class Meta:
        model = Product
        fields = BASIC_EDIT_FIELDS
        widgets = {
            "product_type": forms.Select(attrs={"class": "form-control"}),
            "category": forms.Select(attrs={"class": "form-control"}),
            "name": forms.TextInput(attrs={"class": "form-control", "placeholder": "Product Name"}),
            "slug": forms.TextInput(attrs={"class": "form-control", "placeholder": "product-slug"}),
            "description": forms.Textarea(attrs={"class": "form-control", "rows": 4}),
            "price": forms.NumberInput(attrs={"class": "form-control", "step": "0.01"}),
            "original_price": forms.NumberInput(attrs={"class": "form-control", "step": "0.01"}),
            "material": forms.TextInput(attrs={"class": "form-control"}),
            "is_featured": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "is_bestseller": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "is_active": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["slug"].required = False
        self.fields["original_price"].required = False
        self.fields["description"].required = False
        self.fields["material"].required = False
        active = Category.objects.filter(is_active=True)
        if self.instance and self.instance.pk and self.instance.category_id:
            current = self.instance.category
            if current and not current.is_active:
                active = active | Category.objects.filter(pk=current.pk)
        self.fields["category"].queryset = active.order_by("name")

    def clean(self):
        cleaned_data = super().clean()
        price = cleaned_data.get("price")
        original_price = cleaned_data.get("original_price")
        if original_price and not price:
            raise forms.ValidationError("Selling price is required when original price is set.")
        if original_price and price and original_price <= price:
            raise forms.ValidationError("Original price must be greater than the selling price.")
        return cleaned_data


def validate_product_type_requirements(form, product, color_formset, jewellery_form=None):
    """Validate clothing has ColorVariants, jewellery has JewelleryDetail. Call from view."""
    from django import forms as django_forms
    product_type = form.cleaned_data.get("product_type", "clothing")
    if product_type == "clothing":
        non_deleted = [
            cf for cf in color_formset.forms
            if (cleaned := getattr(cf, "cleaned_data", None)) and not cleaned.get("DELETE")
        ]
        if not non_deleted:
            raise django_forms.ValidationError(
                "Clothing products must have at least one color variant."
            )
    elif product_type == "jewellery":
        if jewellery_form and not jewellery_form.is_valid():
            raise django_forms.ValidationError(
                "Jewellery products require jewellery details (at least metal type)."
            )
        if jewellery_form and jewellery_form.cleaned_data:
            pass
        elif not (product and hasattr(product, "jewellery_detail") and product.jewellery_detail):
            raise django_forms.ValidationError(
                "Jewellery products must have jewellery details (at least metal type)."
            )


class ProductVariantForm(forms.ModelForm):
    class Meta:
        model = ProductVariant
        fields = ["sku", "size", "color", "stock_quantity", "is_active"]
        widgets = {
            "sku": forms.TextInput(attrs={"class": "form-control", "placeholder": "SKU"}),
            "size": forms.TextInput(attrs={"class": "form-control", "placeholder": "Size (e.g., S, M, L)"}),
            "color": forms.TextInput(attrs={"class": "form-control", "placeholder": "Color (optional)"}),
            "stock_quantity": forms.NumberInput(attrs={"class": "form-control", "placeholder": "0", "min": "0"}),
            "is_active": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["color"].required = False
        
        for field_name, field in self.fields.items():
            if field.required and hasattr(field.widget, 'attrs'):
                field.widget.attrs['required'] = 'required'
    
    def clean_sku(self):
        sku = self.cleaned_data.get('sku', '').strip()
        
        if not sku:
            raise forms.ValidationError('SKU is required.')
        
        # Check for duplicate SKU (excluding current instance if editing)
        sku_exists = ProductVariant.objects.filter(sku=sku)
        
        # If updating, exclude current instance
        if self.instance.pk:
            sku_exists = sku_exists.exclude(pk=self.instance.pk)
        
        if sku_exists.exists():
            raise forms.ValidationError('This SKU already exists. Please use a unique SKU.')
        
        return sku
    
    def clean_size(self):
        size = self.cleaned_data.get('size', '').strip()
        
        if not size:
            raise forms.ValidationError('Size is required.')
        
        return size
    
    def clean_stock_quantity(self):
        stock = self.cleaned_data.get('stock_quantity')
        
        if stock is None or stock == '':
            raise forms.ValidationError('Stock quantity is required.')
        
        if stock < 0:
            raise forms.ValidationError('Stock quantity cannot be negative.')
        
        return stock


ProductVariantFormSet = inlineformset_factory(
    Product,
    ProductVariant,
    form=ProductVariantForm,
    extra=3,  # Show 3 empty forms by default
    can_delete=True,
    max_num=50,  # Allow up to 50 variants (different sizes/colors)
)


class ColorVariantForm(forms.ModelForm):
    class Meta:
        model = ColorVariant
        fields = ["name", "color_code", "display_order", "is_active"]
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-control", "placeholder": "e.g. Red, Blue"}),
            "color_code": forms.TextInput(attrs={"class": "form-control", "placeholder": "#hex or leave blank"}),
            "display_order": forms.NumberInput(attrs={"class": "form-control", "min": 0}),
            "is_active": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["color_code"].required = False
        # Allow leaving display_order blank; we'll default it to 0.
        self.fields["display_order"].required = False

    def clean_display_order(self):
        """
        Make display_order optional and default to 0 when left empty.
        This prevents hard validation failures when admins don't care about manual ordering.
        """
        value = self.cleaned_data.get("display_order")
        if value in (None, ""):
            return 0
        return value


def _validate_image_file(image, required=False):
    if not image and not required:
        return image
    if image and hasattr(image, "size"):
        max_size = 5 * 1024 * 1024
        if image.size > max_size:
            raise forms.ValidationError(
                f"Image file size cannot exceed 5MB. Current size: {image.size / (1024 * 1024):.2f}MB"
            )
        try:
            from PIL import Image as PILImage
            img = PILImage.open(image)
            width, height = img.size
            if width * height > 5_000_000:
                raise forms.ValidationError(
                    "Image resolution cannot exceed 5 megapixels. Please resize or compress."
                )
            img.verify()
            image.seek(0)
        except forms.ValidationError:
            raise
        except Exception:
            raise forms.ValidationError(
                "Invalid image file. Please upload a valid image (JPG, PNG, GIF, WebP)."
            )
    return image


class ColorVariantImageForm(forms.ModelForm):
    """One image per ColorVariant. Always use with ColorVariantImageFormSet(instance=<ColorVariant>).
    Do not expose or set color_variant in the form; the formset binds it from the parent instance.
    Only updates image field when a new file is uploaded (avoids unnecessary S3 re-upload).
    """
    class Meta:
        model = ColorVariantImage
        fields = ["image", "is_primary", "alt_text"]
        widgets = {
            "image": forms.FileInput(attrs={"class": "form-control", "accept": "image/*"}),
            "is_primary": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "alt_text": forms.TextInput(attrs={"class": "form-control", "placeholder": "Alt text"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["alt_text"].required = False

    def clean_image(self):
        return _validate_image_file(self.cleaned_data.get("image"), required=not self.instance.pk)

    def save(self, commit=True):
        if getattr(settings, "DEBUG_TRACE", False):
            print("[EDIT %.4fs] TRACE: entering ColorVariantImageForm.save pk=%s" % (time.perf_counter(), getattr(self.instance, "pk", None)))
            print("[EDIT %.4fs] TRACE image changed: %s" % (time.perf_counter(), bool(self.cleaned_data.get("image"))))
        instance = super().save(commit=False)
        # Only update image field if a new file was uploaded (prevents S3 re-upload of unchanged)
        if not self.cleaned_data.get("image") and instance.pk and getattr(self.instance, "image", None):
            instance.image = self.instance.image
        if commit:
            if getattr(settings, "DEBUG_TRACE", False):
                print("[EDIT %.4fs] TRACE: ColorVariantImage save() commit pk=%s" % (time.perf_counter(), instance.pk or "new"))
            logger.debug("Saving image instance %s (ColorVariantImage)", instance.pk or "new")
            instance.save()
            if hasattr(self, "_save_m2m"):
                self._save_m2m()
        return instance


ColorVariantFormSet = inlineformset_factory(
    Product,
    ColorVariant,
    form=ColorVariantForm,
    formset=SafeDeleteInlineFormSet,
    extra=1,
    can_delete=True,
    max_num=20,
)
# Each image is tied to a single ColorVariant. Use with instance=<ColorVariant> only.
# Removed images (DELETE checked) are deleted by formset.save(); no shared image reuse.
ColorVariantImageFormSet = inlineformset_factory(
    ColorVariant,
    ColorVariantImage,
    form=ColorVariantImageForm,
    formset=SafeDeleteInlineFormSet,
    # Strictly enforce max 3 images per color:
    # - At most 3 total forms (existing + empty)
    # - On edit: if 3 images already exist, no extra empty forms are rendered
    # - On create: up to 3 blank slots are shown
    extra=3,
    can_delete=True,
    max_num=3,
)
class SizeVariantForm(forms.ModelForm):
    class Meta:
        model = SizeVariant
        fields = ["size", "stock_quantity", "sku", "is_active"]
        widgets = {
            "size": forms.Select(
                attrs={"class": "form-control"},
                choices=[("", "---------")] + [(s, s) for s in STANDARD_SIZES],
            ),
            "stock_quantity": forms.NumberInput(attrs={"class": "form-control", "min": 0}),
            "sku": forms.TextInput(attrs={"class": "form-control", "placeholder": "Optional SKU"}),
            "is_active": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["sku"].required = False
        
        # Start with all standard sizes
        available_sizes = list(STANDARD_SIZES)
        
        # If editing an existing size variant, get the color variant
        if self.instance and self.instance.pk and self.instance.color_variant_id:
            # Get all sizes already used in this color variant (excluding current instance)
            existing_sizes = SizeVariant.objects.filter(
                color_variant_id=self.instance.color_variant_id
            ).exclude(pk=self.instance.pk).values_list('size', flat=True)
            
            # Remove already-used sizes from available sizes
            available_sizes = [s for s in available_sizes if s not in existing_sizes]
            
            # Always add the current instance's size so it can be edited
            if self.instance.size and self.instance.size not in available_sizes:
                available_sizes.append(self.instance.size)
        elif self.instance and self.instance.color_variant_id and not self.instance.pk:
            # New size variant being added to an existing color variant
            existing_sizes = SizeVariant.objects.filter(
                color_variant_id=self.instance.color_variant_id
            ).values_list('size', flat=True)
            
            # Remove already-used sizes from available sizes
            available_sizes = [s for s in available_sizes if s not in existing_sizes]
        
        # Add custom sizes that might not be in STANDARD_SIZES
        if self.instance and getattr(self.instance, "size", None) and self.instance.size not in STANDARD_SIZES:
            if self.instance.size not in available_sizes:
                available_sizes.append(self.instance.size)
        
        # Create choices list with filtered sizes
        choices = [("", "---------")] + [(s, s) for s in available_sizes]
        self.fields["size"].widget.choices = choices

    def clean(self):
        """
        Allow completely blank extra rows (no size, no stock, no SKU) to be ignored.
        Such rows are marked for deletion so the formset will drop them without errors.
        """
        if getattr(settings, "DEBUG_TRACE", False):
            print("[EDIT %.4fs] TRACE: entering SizeVariantForm.clean pk=%s" % (time.perf_counter(), getattr(self.instance, "pk", None)))
        cleaned_data = super().clean()
        size = (cleaned_data.get("size") or "").strip()
        stock = cleaned_data.get("stock_quantity")
        sku = (cleaned_data.get("sku") or "").strip()

        is_completely_blank = (
            not size
            and (stock is None or stock == "" or stock == 0)
            and not sku
            and not self.instance.pk
        )
        if is_completely_blank:
            # Mark this form as deleted so the inline formset ignores it.
            if "DELETE" in cleaned_data:
                cleaned_data["DELETE"] = True
            # Clear any field-level errors so this row never blocks validation.
            self._errors = {}
        return cleaned_data

    def clean_stock_quantity(self):
        val = self.cleaned_data.get("stock_quantity")
        if val is not None and val < 0:
            raise forms.ValidationError("Stock cannot be negative.")
        return val or 0

    def clean_size(self):
        size = (self.cleaned_data.get("size") or "").strip()
        stock = self.cleaned_data.get("stock_quantity")
        sku = (self.cleaned_data.get("sku") or "").strip()

        # If the entire row is blank, let form.clean() handle marking it as deleted.
        if not size and (stock is None or stock == "" or stock == 0) and not sku and not self.instance.pk:
            return ""

        if not size:
            raise forms.ValidationError("Size is required.")
        if self.instance and self.instance.color_variant_id:
            existing = SizeVariant.objects.filter(
                color_variant_id=self.instance.color_variant_id, size=size
            ).exclude(pk=self.instance.pk)
            if existing.exists():
                raise forms.ValidationError("This size already exists for this color.")
        return size


SizeVariantFormSet = inlineformset_factory(
    ColorVariant,
    SizeVariant,
    form=SizeVariantForm,
    formset=SafeDeleteInlineFormSet,
    extra=1,
    can_delete=True,
    max_num=50,
    min_num=0,
    validate_min=False,
)

