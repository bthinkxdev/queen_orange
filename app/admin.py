from django.contrib import admin

from .models import (
    Address,
    Cart,
    CartItem,
    Category,
    ContactMessage,
    NewsletterSubscription,
    Order,
    OrderItem,
    Payment,
    Product,
    ProductImage,
    ProductVariant,
)


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "is_active")
    prepopulated_fields = {"slug": ("name",)}
    search_fields = ("name",)


class ProductImageInline(admin.TabularInline):
    model = ProductImage
    extra = 0
    fields = ("image", "is_primary", "alt_text")


class ProductVariantInline(admin.TabularInline):
    model = ProductVariant
    extra = 1


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ("name", "category", "price", "is_featured", "is_bestseller", "is_active")
    list_filter = ("category", "is_featured", "is_bestseller", "is_active")
    prepopulated_fields = {"slug": ("name",)}
    search_fields = ("name",)
    fieldsets = (
        ("Basic Information", {
            "fields": ("name", "slug", "category", "description")
        }),
        ("Image", {
            "fields": ("image",)
        }),
        ("Pricing", {
            "fields": ("price", "original_price")
        }),
        ("Jewelry Details", {
            "fields": ("material", "plating_type", "finish", "occasion", "style", "care_instructions")
        }),
        ("Status", {
            "fields": ("is_active", "is_featured", "is_bestseller")
        }),
    )
    inlines = [ProductImageInline, ProductVariantInline]


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
