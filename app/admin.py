from django.contrib import admin

from .models import (
    Address,
    Cart,
    CartItem,
    Category,
    ContactMessage,
    JewelleryDetail,
    JewelleryImage,
    NewsletterSubscription,
    Order,
    OrderItem,
    Payment,
    Product,
    ProductVariant,
    Wishlist,
)


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "is_active")
    prepopulated_fields = {"slug": ("name",)}
    search_fields = ("name",)


class ProductVariantInline(admin.TabularInline):
    model = ProductVariant
    extra = 1


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ("name", "product_type", "category", "price", "is_featured", "is_bestseller", "is_active")
    list_filter = ("category", "is_featured", "is_bestseller", "is_active")
    prepopulated_fields = {"slug": ("name",)}
    search_fields = ("name",)
    inlines = [ProductVariantInline]


@admin.register(JewelleryDetail)
class JewelleryDetailAdmin(admin.ModelAdmin):
    list_display = ("product", "metal_type", "purity", "weight", "stock_quantity")


@admin.register(JewelleryImage)
class JewelleryImageAdmin(admin.ModelAdmin):
    list_display = ("jewellery_detail", "image", "is_primary", "display_order")


@admin.register(Cart)
class CartAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "session_key", "status", "updated_at")
    list_filter = ("status",)


@admin.register(CartItem)
class CartItemAdmin(admin.ModelAdmin):
    list_display = ("cart", "product", "variant", "quantity")


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ("order_number", "display_customer", "display_email", "display_phone", "status", "total", "payment_status", "created_at")
    list_filter = ("status",)
    search_fields = ("order_number", "user__email", "user__username", "address__email", "address__phone", "address__full_name")
    list_select_related = ("address", "user")

    def display_customer(self, obj):
        if obj.user_id is None:
            return "Guest Order"
        return getattr(obj.user, "email", None) or getattr(obj.user, "username", str(obj.user))
    display_customer.short_description = "Customer"

    def display_email(self, obj):
        return (obj.address.email or "—") if obj.address_id else "—"
    display_email.short_description = "Email"

    def display_phone(self, obj):
        return (obj.address.phone or "—") if obj.address_id else "—"
    display_phone.short_description = "Phone"

    def payment_status(self, obj):
        try:
            return obj.payment.get_status_display() if getattr(obj, "payment", None) else "—"
        except Exception:
            return "—"
    payment_status.short_description = "Payment"


@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    list_display = ("order", "product_name", "quantity", "unit_price")


@admin.register(Address)
class AddressAdmin(admin.ModelAdmin):
    list_display = ("full_name", "city", "state", "is_snapshot")


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ("order", "method", "status", "amount", "processed_at")
    list_select_related = ("order", "order__address", "order__user")


@admin.register(ContactMessage)
class ContactMessageAdmin(admin.ModelAdmin):
    list_display = ("name", "email", "subject", "is_resolved", "created_at")
    list_filter = ("is_resolved",)


@admin.register(NewsletterSubscription)
class NewsletterSubscriptionAdmin(admin.ModelAdmin):
    list_display = ("email", "is_active", "created_at")


@admin.register(Wishlist)
class WishlistAdmin(admin.ModelAdmin):
    list_display = ("user", "color_variant", "created_at")
    list_filter = ("created_at",)
    search_fields = ("user__email", "user__username", "color_variant__product__name", "color_variant__name")
    readonly_fields = ("user", "color_variant", "created_at", "updated_at")
    ordering = ("-created_at",)

    def has_add_permission(self, request):
        return False
from .models import ColorVariantImage, Review, SizeVariant, ColorVariant
admin.site.register(ColorVariantImage)
admin.site.register(Review)
admin.site.register(SizeVariant)
admin.site.register(ColorVariant)
