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
    list_display = ("order_number", "user", "status", "total", "created_at")
    list_filter = ("status",)
    search_fields = ("order_number", "user__username")


@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    list_display = ("order", "product_name", "quantity", "unit_price")


@admin.register(Address)
class AddressAdmin(admin.ModelAdmin):
    list_display = ("full_name", "city", "state", "is_snapshot")


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ("order", "method", "status", "amount", "processed_at")


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
