from django.conf import settings
from django.contrib.auth.models import User
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Avg, Count
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.utils import timezone
from django.utils.text import slugify
import hashlib
import secrets
import string
import random


class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class Category(TimeStampedModel):
    name = models.CharField(max_length=120, unique=True)
    slug = models.SlugField(max_length=140, unique=True)
    is_active = models.BooleanField(default=True, db_index=True)
    image = models.ImageField(upload_to="categories/", blank=True, null=True)

    class Meta:
        ordering = ["name"]
        indexes = [
            models.Index(fields=["is_active", "name"]),
        ]

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.name)
            self.slug = base_slug
            
            # Handle duplicate slugs by appending 4-character random string
            while Category.objects.filter(slug=self.slug).exclude(pk=self.pk).exists():
                random_suffix = ''.join(random.choices(string.ascii_lowercase + string.digits, k=4))
                self.slug = f"{base_slug}-{random_suffix}"
        
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class ProductQuerySet(models.QuerySet):
    def active(self):
        return self.filter(is_active=True)

    def available(self):
        from django.db.models import Q
        return self.active().filter(
            Q(variants__is_active=True, variants__stock_quantity__gt=0)
            | Q(
                color_variants__is_active=True,
                color_variants__size_variants__is_active=True,
                color_variants__size_variants__stock_quantity__gt=0,
            )
            | Q(product_type=PRODUCT_TYPE_JEWELLERY, jewellery_detail__stock_quantity__gt=0)
        ).distinct()


PRODUCT_TYPE_CLOTHING = "clothing"
PRODUCT_TYPE_JEWELLERY = "jewellery"
PRODUCT_TYPE_CHOICES = [
    (PRODUCT_TYPE_CLOTHING, "Clothing"),
    (PRODUCT_TYPE_JEWELLERY, "Jewellery"),
]


class Product(TimeStampedModel):
    """Product has no direct image field for clothing. Images live on ColorVariant (ColorVariantImage).
    For jewellery, images come from JewelleryDetail.
    Use product.get_card_image_urls() or color_variant.images for display; never product.images.
    """
    product_type = models.CharField(
        max_length=20,
        choices=PRODUCT_TYPE_CHOICES,
        default=PRODUCT_TYPE_CLOTHING,
        db_index=True,
    )
    category = models.ForeignKey(Category, on_delete=models.PROTECT, related_name="products")
    name = models.CharField(max_length=200, db_index=True)
    slug = models.SlugField(max_length=220, unique=True)
    description = models.TextField(blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)])
    original_price = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)], blank=True, null=True)
    # Optional material information (for filtering on collection page)
    material = models.CharField(max_length=120, blank=True)
    # Flag + optional date window for Deal Of The Day
    is_featured = models.BooleanField(default=False, db_index=True)
    is_bestseller = models.BooleanField(default=False, db_index=True)
    is_deal_of_day = models.BooleanField(default=False, db_index=True)
    deal_of_day_start = models.DateField(blank=True, null=True, db_index=True)
    deal_of_day_end = models.DateField(blank=True, null=True, db_index=True)
    is_active = models.BooleanField(default=True, db_index=True)

    # Aggregated ratings (from approved, non-deleted reviews only)
    average_rating = models.DecimalField(
        max_digits=3,
        decimal_places=2,
        default=0,
        help_text="Average star rating from verified reviews (1-5).",
    )
    total_reviews = models.PositiveIntegerField(
        default=0,
        help_text="Total number of approved, non-deleted reviews.",
    )

    objects = ProductQuerySet.as_manager()

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["is_active", "is_featured"]),
            models.Index(fields=["is_active", "is_bestseller"]),
            models.Index(fields=["is_active", "is_deal_of_day"]),
            models.Index(fields=["is_active", "material"]),
            models.Index(fields=["category", "is_active"]),
        ]

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.name)
            self.slug = base_slug
            
            # Handle duplicate slugs by appending 4-character random string
            while Product.objects.filter(slug=self.slug).exclude(pk=self.pk).exists():
                random_suffix = ''.join(random.choices(string.ascii_lowercase + string.digits, k=4))
                self.slug = f"{base_slug}-{random_suffix}"
        
        super().save(*args, **kwargs)

    @property
    def discount_percent(self):
        if self.original_price and self.original_price > self.price:
            return round(((self.original_price - self.price) / self.original_price) * 100)
        return 0

    def _normalize_card_image_url(self, url):
        """Ensure image URL is loadable: add https:// for host-only or protocol-relative URLs."""
        if not url or not isinstance(url, str):
            return url
        url = url.strip()
        if url.startswith("http://") or url.startswith("https://"):
            return url
        # Paths like /media/... are same-origin; leave as-is
        if url.startswith("/"):
            # If stored as /media/i1.ytimg.com/... (external URL in DB), convert to https
            if "/media/" in url and "ytimg.com" in url:
                base = getattr(settings, "MEDIA_URL", "/media/").rstrip("/")
                if url.startswith(base + "/"):
                    return "https://" + url[len(base) + 1:]
            return url
        # Host-only or protocol-relative (e.g. i1.ytimg.com/vi/.../hqdefault.jpg)
        return "https://" + url.lstrip("/")
    def has_any_sellable_stock(self):
        """
        True if product has in-stock ProductVariant OR in-stock SizeVariant (via color_variants)
        OR is jewellery with JewelleryDetail.stock_quantity > 0.
        """
        if getattr(self, "_has_sellable_stock", None) is not None:
            return self._has_sellable_stock
        if getattr(self, "product_type", None) == PRODUCT_TYPE_JEWELLERY:
            try:
                jd = getattr(self, "jewellery_detail", None)
                if jd and (getattr(jd, "stock_quantity", 0) or 0) > 0:
                    self._has_sellable_stock = True
                    return True
            except Exception:
                pass
            self._has_sellable_stock = False
            return False
        # ProductVariant: use prefetch (HomeView prefetches in-stock variants only)
        pv_list = list(self.variants.all())
        if any(v for v in pv_list if getattr(v, "is_active", True) and (getattr(v, "stock_quantity", 0) or 0) > 0):
            self._has_sellable_stock = True
            return True
        # SizeVariant: use prefetched color_variants__size_variants when available
        for cv in self.color_variants.all():
            if not getattr(cv, "is_active", True):
                continue
            for sv in cv.size_variants.all():
                if getattr(sv, "is_active", True) and (getattr(sv, "stock_quantity", 0) or 0) > 0:
                    self._has_sellable_stock = True
                    return True
        self._has_sellable_stock = False
        return False

    def get_card_image_urls(self, limit=20):
        """
        Ordered list of image URLs for product cards (hover/touch slider on home and collections).
        Clothing: one image per color variant.
        Jewellery: main image from JewelleryDetail.
        """
        urls = []
        seen = set()
        try:
            if getattr(self, "product_type", None) == PRODUCT_TYPE_JEWELLERY:
                try:
                    jd = getattr(self, "jewellery_detail", None)
                    if jd:
                        urls = []
                        for img in jd.images.order_by("display_order", "id")[:3]:
                            if img.image:
                                url = img.image.url
                                if url:
                                    url = self._normalize_card_image_url(url)
                                if url:
                                    urls.append(url)
                        return urls[:3]
                except Exception:
                    pass
                return []

            for cv in self.color_variants.filter(is_active=True).order_by("display_order", "name"):
                if len(urls) >= limit:
                    break
                first_img = cv.images.filter(image__isnull=False).exclude(image="").first()
                if first_img and first_img.image:
                    url = first_img.image.url
                    if url:
                        url = self._normalize_card_image_url(url)
                    if url and url not in seen:
                        seen.add(url)
                        urls.append(url)
        except Exception:
            pass
        return urls[:limit] if urls else []

    def __str__(self):
        return self.name


class ColorVariant(TimeStampedModel):
    """Color option for a product (e.g. Red, Blue). Has multiple images and size variants."""
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="color_variants")
    name = models.CharField(max_length=60)
    color_code = models.CharField(max_length=20, blank=True, help_text="Optional hex or name for swatch (e.g. #FF0000)")
    display_order = models.PositiveIntegerField(default=0, db_index=True)
    is_active = models.BooleanField(default=True, db_index=True)

    class Meta:
        ordering = ["display_order", "name", "id"]
        constraints = [
            models.UniqueConstraint(fields=["product", "name"], name="unique_product_color"),
        ]
        indexes = [
            models.Index(fields=["product", "display_order"]),
        ]

    def __str__(self):
        return f"{self.product.name} - {self.name}"


class ColorVariantImage(TimeStampedModel):
    """Image for a specific color variant."""
    color_variant = models.ForeignKey(
        ColorVariant, on_delete=models.CASCADE, related_name="images"
    )
    image = models.ImageField(upload_to="products/color_images/")
    is_primary = models.BooleanField(default=False, db_index=True)
    alt_text = models.CharField(max_length=200, blank=True)

    class Meta:
        ordering = ["-is_primary", "id"]
        indexes = [
            models.Index(fields=["color_variant", "is_primary"]),
        ]

    def __str__(self):
        return f"{self.color_variant} image"


class SizeVariant(TimeStampedModel):
    """Size option under a color with its own stock.
    One size per (color_variant, size); stock is per color. Editing one color cannot affect another.
    """
    color_variant = models.ForeignKey(
        ColorVariant, on_delete=models.CASCADE, related_name="size_variants"
    )
    size = models.CharField(max_length=20)
    stock_quantity = models.PositiveIntegerField(default=0)
    sku = models.CharField(max_length=64, unique=True, blank=True, null=True)
    is_active = models.BooleanField(default=True, db_index=True)

    class Meta:
        ordering = ["size"]
        constraints = [
            models.UniqueConstraint(
                fields=["color_variant", "size"], name="unique_color_size"
            ),
            models.CheckConstraint(
                condition=models.Q(stock_quantity__gte=0), name="sizevariant_stock_non_negative"
            ),
        ]
        indexes = [
            models.Index(fields=["color_variant", "is_active", "stock_quantity"]),
        ]

    @property
    def product(self):
        return self.color_variant.product

    def __str__(self):
        return f"{self.color_variant} - {self.size}"


class ProductVariant(TimeStampedModel):
    """Legacy variant (product+size+color). Kept for backward compatibility and cart/order history."""
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="variants")
    sku = models.CharField(max_length=64, unique=True, blank=True, null=True)
    size = models.CharField(max_length=20)
    color = models.CharField(max_length=30, blank=True)
    stock_quantity = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True, db_index=True)
    legacy_size_variant = models.OneToOneField(
        SizeVariant,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="legacy_product_variant",
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["product", "size", "color"], name="unique_variant"),
            models.CheckConstraint(condition=models.Q(stock_quantity__gte=0), name="stock_non_negative"),
        ]
        indexes = [
            models.Index(fields=["product", "is_active", "stock_quantity"]),
        ]

    def __str__(self):
        color = f" / {self.color}" if self.color else ""
        return f"{self.product.name} - {self.size}{color}"


class JewelleryDetail(TimeStampedModel):
    """Details specific to jewellery products. No color/size variants.
    Images: use JewelleryImage (max 3 per product)."""
    product = models.OneToOneField(
        Product, on_delete=models.CASCADE, related_name="jewellery_detail"
    )
    metal_type = models.CharField(max_length=80)
    purity = models.CharField(max_length=40, blank=True, null=True, help_text="e.g. 18K, 22K, 92.5% (optional)")
    weight = models.DecimalField(
        max_digits=10, decimal_places=3,
        help_text="Weight in grams (optional)",
        validators=[MinValueValidator(0)],
        blank=True,
        null=True,
    )
    gemstone = models.CharField(max_length=120, blank=True)
    making_charge = models.DecimalField(
        max_digits=10, decimal_places=2,
        validators=[MinValueValidator(0)],
        blank=True,
        null=True,
        help_text="Optional",
    )
    is_adjustable = models.BooleanField(default=False)
    stock_quantity = models.PositiveIntegerField(
        default=1,
        help_text="Available quantity; jewellery is typically one per SKU",
    )

    class Meta:
        verbose_name = "Jewellery detail"
        verbose_name_plural = "Jewellery details"

    def __str__(self):
        return f"{self.product.name} (Jewellery)"


class JewelleryImage(TimeStampedModel):
    """Image for jewellery product. Maximum 3 per JewelleryDetail."""
    jewellery_detail = models.ForeignKey(
        JewelleryDetail, on_delete=models.CASCADE, related_name="images"
    )
    image = models.ImageField(upload_to="products/jewellery/")
    is_primary = models.BooleanField(default=False, db_index=True)
    display_order = models.PositiveIntegerField(default=0, db_index=True)

    class Meta:
        ordering = ["display_order", "id"]

    def __str__(self):
        return f"{self.jewellery_detail.product.name} image"


class Cart(TimeStampedModel):
    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        ORDERED = "ordered", "Ordered"
        ABANDONED = "abandoned", "Abandoned"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, blank=True, null=True, related_name="carts")
    session_key = models.CharField(max_length=40, blank=True, db_index=True)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.ACTIVE, db_index=True)

    class Meta:
        indexes = [
            models.Index(fields=["user", "status"]),
            models.Index(fields=["session_key", "status"]),
        ]

    def __str__(self):
        return f"Cart {self.pk} ({self.status})"

    @property
    def subtotal(self):
        return sum(item.line_total for item in self.items.select_related("product"))


class CartItem(TimeStampedModel):
    cart = models.ForeignKey(Cart, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name="cart_items")
    variant = models.ForeignKey(
        ProductVariant, on_delete=models.PROTECT, related_name="cart_items",
        null=True, blank=True,
    )
    size_variant = models.ForeignKey(
        SizeVariant, on_delete=models.PROTECT, related_name="cart_items",
        null=True, blank=True,
    )
    quantity = models.PositiveIntegerField(default=1, validators=[MinValueValidator(1)])
    unit_price = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)])

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["cart", "variant"],
                name="unique_cart_variant",
                condition=models.Q(variant__isnull=False),
            ),
            models.UniqueConstraint(
                fields=["cart", "size_variant"],
                name="unique_cart_size_variant",
                condition=models.Q(size_variant__isnull=False),
            ),
            models.UniqueConstraint(
                fields=["cart", "product"],
                name="unique_cart_product_jewellery",
                condition=models.Q(variant__isnull=True, size_variant__isnull=True),
            ),
            models.CheckConstraint(condition=models.Q(quantity__gte=1), name="cartitem_qty_positive"),
            # Either variant, size_variant, or product-only (jewellery). Jewellery enforced in Python.
        ]
        indexes = [
            models.Index(fields=["cart", "product"]),
        ]

    def get_sellable(self):
        """Return the sellable unit (SizeVariant, ProductVariant, or None for product-only jewellery)."""
        if self.size_variant_id:
            return self.size_variant
        if self.variant_id:
            return self.variant
        return None

    @property
    def variant_display(self):
        """Human-readable variant (size / color) or jewellery info for display."""
        sellable = self.get_sellable()
        if sellable:
            if hasattr(sellable, "color_variant"):
                return f"{sellable.size} / {sellable.color_variant.name}"
            return f"{sellable.size} {getattr(sellable, 'color', '') or ''}".strip() or sellable.size
        # Product-only (jewellery)
        if self.product_id and getattr(self.product, "product_type", None) == PRODUCT_TYPE_JEWELLERY:
            try:
                jd = getattr(self.product, "jewellery_detail", None)
                if jd:
                    purity = (jd.purity or "").strip()
                    return f"{jd.metal_type} {purity}".strip() if purity else jd.metal_type
            except Exception:
                pass
        return ""

    @property
    def line_total(self):
        return self.unit_price * self.quantity

    def __str__(self):
        return f"{self.product.name} x {self.quantity}"


class Address(TimeStampedModel):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, blank=True, null=True, related_name="addresses")
    full_name = models.CharField(max_length=120)
    phone = models.CharField(max_length=20)
    email = models.EmailField(blank=True)
    address_line = models.TextField()
    city = models.CharField(max_length=80)
    state = models.CharField(max_length=80)
    pincode = models.CharField(max_length=10)
    is_default = models.BooleanField(default=False, db_index=True)
    is_snapshot = models.BooleanField(default=False, db_index=True)

    class Meta:
        indexes = [
            models.Index(fields=["user", "is_default"]),
        ]

    def __str__(self):
        return f"{self.full_name} - {self.city}"


class Order(TimeStampedModel):
    class Status(models.TextChoices):
        PLACED = "placed", "Placed"
        CONFIRMED = "confirmed", "Confirmed"
        SHIPPED = "shipped", "Shipped"
        DELIVERED = "delivered", "Delivered"
        CANCELLED = "cancelled", "Cancelled"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, blank=True, null=True, related_name="orders")
    order_number = models.CharField(max_length=20, unique=True, db_index=True)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.PLACED, db_index=True)
    subtotal = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)])
    shipping = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)])
    total = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)])
    address = models.ForeignKey(Address, on_delete=models.PROTECT, related_name="orders")

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.order_number


class OrderItem(TimeStampedModel):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name="order_items")
    variant = models.ForeignKey(
        ProductVariant, on_delete=models.PROTECT, related_name="order_items",
        null=True, blank=True,
    )
    size_variant = models.ForeignKey(
        SizeVariant, on_delete=models.PROTECT, related_name="order_items",
        null=True, blank=True,
    )
    product_name = models.CharField(max_length=200)
    variant_snapshot = models.CharField(max_length=60)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)])
    quantity = models.PositiveIntegerField(default=1, validators=[MinValueValidator(1)])

    def get_sellable(self):
        """Return the sellable unit (SizeVariant or ProductVariant) for stock deduction."""
        if self.size_variant_id:
            return self.size_variant
        return self.variant

    @property
    def line_total(self):
        return self.unit_price * self.quantity

    def __str__(self):
        return f"{self.order.order_number} - {self.product_name}"


class Payment(TimeStampedModel):
    class Method(models.TextChoices):
        COD = "cod", "Cash on Delivery"
        WHATSAPP = "whatsapp", "WhatsApp Order"
        RAZORPAY = "razorpay", "Online Payment"

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        PAID = "paid", "Paid"
        FAILED = "failed", "Failed"

    order = models.OneToOneField(Order, on_delete=models.CASCADE, related_name="payment")
    method = models.CharField(max_length=20, choices=Method.choices, default=Method.COD, db_index=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING, db_index=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)])
    processed_at = models.DateTimeField(blank=True, null=True)
    razorpay_order_id = models.CharField(max_length=255, blank=True, null=True, db_index=True)
    razorpay_payment_id = models.CharField(max_length=255, blank=True, null=True, db_index=True)
    razorpay_signature = models.CharField(max_length=255, blank=True, null=True)

    def mark_paid(self):
        self.status = self.Status.PAID
        self.processed_at = timezone.now()
        self.save(update_fields=["status", "processed_at"])


class ContactMessage(TimeStampedModel):
    name = models.CharField(max_length=120)
    email = models.EmailField()
    subject = models.CharField(max_length=200)
    message = models.TextField()
    is_resolved = models.BooleanField(default=False, db_index=True)

    def __str__(self):
        return f"{self.name} - {self.subject}"


class NewsletterSubscription(TimeStampedModel):
    email = models.EmailField(unique=True)
    is_active = models.BooleanField(default=True, db_index=True)

    def __str__(self):
        return self.email


class Wishlist(TimeStampedModel):
    """User wishlist: ColorVariant for clothing, Product for jewellery."""
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="wishlist_items",
    )
    color_variant = models.ForeignKey(
        "ColorVariant",
        on_delete=models.CASCADE,
        related_name="wishlisted_by",
        null=True,
        blank=True,
    )
    product = models.ForeignKey(
        "Product",
        on_delete=models.CASCADE,
        related_name="wishlisted_by",
        null=True,
        blank=True,
    )

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "color_variant"],
                condition=models.Q(color_variant__isnull=False),
                name="unique_user_color_variant_wishlist",
            ),
            models.UniqueConstraint(
                fields=["user", "product"],
                condition=models.Q(product__isnull=False),
                name="unique_user_product_wishlist",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(product__isnull=False, color_variant__isnull=True)
                    | models.Q(product__isnull=True, color_variant__isnull=False)
                ),
                name="wishlist_product_or_variant",
            ),
        ]
        indexes = [
            models.Index(fields=["user"]),
        ]

    def __str__(self):
        if self.color_variant_id:
            return f"{self.user} - {self.color_variant}"
        return f"{self.user} - {self.product}"


class UserProfile(TimeStampedModel):
    """Extended user profile for additional user information"""
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='profile')
    phone = models.CharField(max_length=20, blank=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['user']),
        ]
    
    def __str__(self):
        return f"Profile: {self.user.email}"


class Banner(TimeStampedModel):
    """Home page banner for carousel. Maximum number of active banners enforced at save."""
    MAX_ACTIVE = 5

    title = models.CharField(max_length=200, blank=True)
    subtitle = models.CharField(max_length=300, blank=True)
    image = models.ImageField(upload_to="banners/")
    redirect_url = models.URLField(max_length=500, blank=True, null=True)
    is_active = models.BooleanField(default=True, db_index=True)
    display_order = models.PositiveIntegerField(default=0, db_index=True)

    class Meta:
        ordering = ["display_order", "created_at"]
        indexes = [
            models.Index(fields=["is_active", "display_order"]),
        ]

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        active = (
            Banner.objects.filter(is_active=True)
            .order_by("display_order", "created_at")
        )
        if active.count() > self.MAX_ACTIVE:
            to_deactivate = active[self.MAX_ACTIVE:]
            Banner.objects.filter(pk__in=to_deactivate.values_list("pk", flat=True)).update(
                is_active=False
            )

    def __str__(self):
        return self.title or f"Banner #{self.pk}"


class OTPRequest(TimeStampedModel):
    """Store OTP requests for email-based authentication"""
    email = models.EmailField(db_index=True)
    otp_hash = models.CharField(max_length=64)  # SHA256 hash of OTP
    expires_at = models.DateTimeField(db_index=True)
    is_used = models.BooleanField(default=False, db_index=True)
    ip_address = models.GenericIPAddressField(blank=True, null=True)
    attempts = models.PositiveIntegerField(default=0)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['email', 'is_used', 'expires_at']),
            models.Index(fields=['created_at', 'email']),
        ]
    
    def __str__(self):
        return f"OTP for {self.email} - {'Used' if self.is_used else 'Active'}"
    
    @staticmethod
    def hash_otp(otp):
        """Hash OTP using SHA256"""
        return hashlib.sha256(str(otp).encode()).hexdigest()
    
    def verify_otp(self, otp):
        """Verify provided OTP against stored hash"""
        return self.otp_hash == self.hash_otp(otp)
    
    def is_valid(self):
        """Check if OTP is still valid (not expired, not used)"""
        return not self.is_used and timezone.now() < self.expires_at
    
    @classmethod
    def generate_otp(cls):
        """Generate a secure 4-digit OTP"""
        return str(secrets.randbelow(10000)).zfill(4)


class Review(TimeStampedModel):
    """
    Product review from a verified buyer.

    Business rules:
    - Only logged-in users can create reviews (enforced in views).
    - User must have at least one delivered order for the product.
    - One review per (product, user).
    - Rating is 1–5 stars.
    - Reviews can be moderated via is_approved.
    - Reviews are soft-deleted via is_deleted flag.
    """

    product = models.ForeignKey(
        Product,
        on_delete=models.PROTECT,
        related_name="reviews",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="reviews",
        null=True,
        blank=True,
    )
    order = models.ForeignKey(
        "Order",
        on_delete=models.SET_NULL,
        related_name="reviews",
        null=True,
        blank=True,
        help_text="The delivered order that verified this review.",
    )
    rating = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)],
    )
    title = models.CharField(max_length=200, blank=True)
    comment = models.TextField(blank=True)
    is_approved = models.BooleanField(
        default=True,
        db_index=True,
        help_text="Only approved reviews are shown on the storefront.",
    )
    is_deleted = models.BooleanField(
        default=False,
        db_index=True,
        help_text="Soft delete flag; deleted reviews are hidden but kept for history.",
    )

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["product", "user"],
                name="unique_product_user_review",
            ),
            # Use `condition=` for compatibility with the project's Django version
            models.CheckConstraint(
                condition=models.Q(rating__gte=1) & models.Q(rating__lte=5),
                name="review_rating_between_1_and_5",
            ),
        ]
        indexes = [
            models.Index(fields=["product"]),
            models.Index(fields=["rating"]),
            models.Index(fields=["is_approved"]),
            models.Index(fields=["product", "is_approved"]),
        ]

    def __str__(self):
        uname = getattr(self.user, "username", "Anonymous")
        return f"Review for {self.product} by {uname} ({self.rating}★)"


def _recompute_product_rating(product_id: int):
    """
    Efficiently recompute average rating and total reviews for a single product.
    Only considers approved, non-deleted reviews.
    """
    if not product_id:
        return
    qs = Review.objects.filter(
        product_id=product_id,
        is_approved=True,
        is_deleted=False,
    )
    agg = qs.aggregate(
        avg=Avg("rating"),
        cnt=Count("id"),
    )
    avg = agg["avg"] or 0
    cnt = agg["cnt"] or 0
    # Update only the two fields for this product
    Product.objects.filter(pk=product_id).update(
        average_rating=avg,
        total_reviews=cnt,
    )


@receiver(post_save, sender=Review)
def review_post_save(sender, instance: Review, **kwargs):
    """
    Recompute product aggregates whenever a review is created or updated
    (e.g. approval status changed, soft-deleted).
    """
    _recompute_product_rating(instance.product_id)


@receiver(post_delete, sender=Review)
def review_post_delete(sender, instance: Review, **kwargs):
    """
    Support physical deletions as well (e.g. if ever used).
    """
    _recompute_product_rating(instance.product_id)
