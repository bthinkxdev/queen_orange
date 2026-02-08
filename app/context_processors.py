from .models import Wishlist
from .services import CartService


def cart_context(request):
    try:
        cart = CartService.get_or_create_cart(request)
        cart_count = sum(item.quantity for item in cart.items.all())
    except Exception:
        cart_count = 0
    return {
        "cart_count": cart_count,
    }


def wishlist_context(request):
    wishlist_count = 0
    wishlist_product_ids = []
    if getattr(request, "user", None) and request.user.is_authenticated:
        wishlist_product_ids = list(
            Wishlist.objects.filter(user=request.user, product__is_active=True).values_list("product_id", flat=True)
        )
        wishlist_count = len(wishlist_product_ids)
    return {
        "wishlist_count": wishlist_count,
        "wishlist_product_ids": wishlist_product_ids,
    }

