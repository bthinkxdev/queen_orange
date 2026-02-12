import threading
from dataclasses import dataclass

from django.conf import settings
from django.core.mail import send_mail
from django.db import transaction
from django.db.models import F
from django.template.loader import render_to_string
from django.utils.crypto import get_random_string

from .models import (
    Address,
    Cart,
    CartItem,
    JewelleryDetail,
    Order,
    OrderItem,
    Payment,
    Product,
    ProductVariant,
    SizeVariant,
)


def send_order_notification_email_async(order, request=None):
    """Send order notification email asynchronously in a background thread."""
    thread = threading.Thread(
        target=send_order_notification_email,
        args=(order, request),
        daemon=True
    )
    thread.start()
    return thread


def send_order_notification_email(order, request=None):
    """Send order notification email to admin/owner when a new order is placed."""
    try:
        admin_emails = getattr(settings, 'ADMIN_NOTIFICATION_EMAILS', [])
        if not admin_emails:
            return False
        
        try:
            if request:
                order_url = request.build_absolute_uri(f'/dashboard/orders/{order.order_number}/')
            else:
                site_domain = getattr(settings, 'SITE_DOMAIN', 'https://queenorange.shop/')
                order_url = f"{site_domain}/dashboard/orders/{order.order_number}/"
        except Exception:
            order_url = f"Order #{order.order_number}"

        payment_method = "Cash on Delivery"
        try:
            if hasattr(order, 'payment') and order.payment:
                payment_method = order.payment.get_method_display()
        except Exception:
            pass
        
        context = {
            'order': order,
            'order_url': order_url,
            'payment_method': payment_method,
            'site_name': ' Queen Orange',
        }
        
        try:
            html_message = render_to_string('admin/order_notification_email.html', context)
            plain_message = render_to_string('admin/order_notification_email.txt', context)
        except Exception:
            return False
        
        try:
            send_mail(
                subject=f'New Order #{order.order_number} - ₹{order.total}',
                message=plain_message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=admin_emails,
                html_message=html_message,
                fail_silently=False,
            )
            return True
        except Exception:
            return False
    except Exception:
        return False


class CartError(Exception):
    pass


class StockError(CartError):
    pass


@dataclass
class CartTotals:
    subtotal: object
    shipping: object
    total: object


class CartService:
    @staticmethod
    def _ensure_session_key(request):
        if not request.session.session_key:
            request.session.save()
        return request.session.session_key

    @classmethod
    def get_or_create_cart(cls, request):
        user = getattr(request, "user", None)
        user = user if (user and user.is_authenticated) else None
        if user:
            cart, _ = Cart.objects.get_or_create(user=user, status=Cart.Status.ACTIVE)
            return cart
        session_key = cls._ensure_session_key(request)
        cart, _ = Cart.objects.get_or_create(session_key=session_key, status=Cart.Status.ACTIVE)
        return cart

    @classmethod
    def merge_carts(cls, user, session_key):
        if not user or not session_key:
            return
        try:
            session_cart = Cart.objects.get(session_key=session_key, status=Cart.Status.ACTIVE)
        except Cart.DoesNotExist:
            return
        user_cart, _ = Cart.objects.get_or_create(user=user, status=Cart.Status.ACTIVE)
        for item in session_cart.items.select_related("product", "variant", "size_variant").all():
            sellable = item.get_sellable()
            if sellable:
                cls.add_item(user_cart, sellable, item.quantity)
            elif item.product_id and item.product.product_type == "jewellery":
                cls.add_item(user_cart, item.product, item.quantity)
        session_cart.status = Cart.Status.ABANDONED
        session_cart.save(update_fields=["status"])

    @staticmethod
    def compute_totals(cart):
        try:
            subtotal = sum(item.line_total for item in cart.items.select_related("product"))
            shipping_threshold = getattr(settings, "FREE_SHIPPING_THRESHOLD", 999)
            shipping_fee = getattr(settings, "FLAT_SHIPPING_FEE", 50)
            shipping = 0 if subtotal >= shipping_threshold else shipping_fee
            total = subtotal + shipping
            return CartTotals(subtotal=subtotal, shipping=shipping, total=total)
        except Exception:
            return CartTotals(subtotal=0, shipping=0, total=0)

    @staticmethod
    def add_item(cart, variant_or_size_variant_or_product, quantity):
        """Add to cart. Accepts ProductVariant, SizeVariant, or Product (for jewellery)."""
        try:
            v = variant_or_size_variant_or_product
            if isinstance(v, Product):
                product = v
                jd = getattr(product, "jewellery_detail", None)
                if not jd or product.product_type != "jewellery":
                    raise CartError("Product is not a jewellery item.")
                stock = jd.stock_quantity or 0
                if stock <= 0:
                    raise StockError("This item is out of stock.")
                max_qty = getattr(settings, "MAX_CART_QTY", 10)
                quantity = max(1, min(quantity, max_qty))
                if quantity > stock:
                    raise StockError("Requested quantity exceeds available stock.")
                item = CartItem.objects.filter(
                    cart=cart, product=product, variant__isnull=True, size_variant__isnull=True
                ).first()
                if item:
                    new_quantity = min(item.quantity + quantity, max_qty)
                    if new_quantity > stock:
                        raise StockError("Requested quantity exceeds available stock.")
                    item.quantity = new_quantity
                    item.unit_price = product.price
                    item.save(update_fields=["quantity", "unit_price", "updated_at"])
                    return item
                return CartItem.objects.create(
                    cart=cart,
                    product=product,
                    quantity=quantity,
                    unit_price=product.price,
                )

            product = v.product
            if not getattr(v, "is_active", True) or (v.stock_quantity or 0) <= 0:
                raise StockError("This item is out of stock.")
            max_qty = getattr(settings, "MAX_CART_QTY", 10)
            quantity = max(1, min(quantity, max_qty))
            if quantity > v.stock_quantity:
                raise StockError("Requested quantity exceeds available stock.")
            is_size_variant = isinstance(v, SizeVariant)
            if is_size_variant:
                item = CartItem.objects.filter(cart=cart, size_variant=v).first()
            else:
                item = CartItem.objects.filter(cart=cart, variant=v).first()
            if item:
                new_quantity = min(item.quantity + quantity, max_qty)
                if new_quantity > v.stock_quantity:
                    raise StockError("Requested quantity exceeds available stock.")
                item.quantity = new_quantity
                item.unit_price = product.price
                item.save(update_fields=["quantity", "unit_price", "updated_at"])
                return item
            if is_size_variant:
                return CartItem.objects.create(
                    cart=cart,
                    size_variant=v,
                    product=product,
                    quantity=quantity,
                    unit_price=product.price,
                )
            return CartItem.objects.create(
                cart=cart,
                variant=v,
                product=product,
                quantity=quantity,
                unit_price=product.price,
            )
        except StockError:
            raise
        except CartError:
            raise
        except Exception as e:
            raise CartError(f"Failed to add item to cart: {str(e)}")

    @staticmethod
    def update_item(item, quantity):
        try:
            if quantity <= 0:
                item.delete()
                return
            sellable = item.get_sellable()
            if sellable:
                stock = sellable.stock_quantity
                product = sellable.product
            else:
                if not item.product_id:
                    raise CartError("Invalid cart item.")
                product = item.product
                if product.product_type == "jewellery":
                    jd = getattr(product, "jewellery_detail", None)
                    stock = (jd.stock_quantity or 0) if jd else 0
                else:
                    raise CartError("Invalid cart item.")
            max_qty = getattr(settings, "MAX_CART_QTY", 10)
            quantity = min(quantity, max_qty)
            if quantity > stock:
                raise StockError("Requested quantity exceeds available stock.")
            item.quantity = quantity
            item.unit_price = product.price
            item.save(update_fields=["quantity", "unit_price", "updated_at"])
        except StockError:
            raise
        except CartError:
            raise
        except Exception as e:
            raise CartError(f"Failed to update cart item: {str(e)}")


class OrderService:
    @staticmethod
    def _generate_order_number():
        while True:
            order_number = f"QO{get_random_string(8).upper()}"
            if not Order.objects.filter(order_number=order_number).exists():
                return order_number

    @classmethod
    @transaction.atomic
    def create_order(cls, cart, form_data, user=None, clear_cart=True):
        items = (
            cart.items.select_related("variant", "size_variant", "product")
            .select_for_update(of=("self",))
            .all()
        )
        if not items:
            raise CartError("Cart is empty.")

        for item in items:
            sellable = item.get_sellable()
            if sellable:
                if item.quantity > sellable.stock_quantity:
                    raise StockError(f"{item.product.name} is out of stock.")
            else:
                if item.product.product_type == "jewellery":
                    jd = getattr(item.product, "jewellery_detail", None)
                    if not jd or item.quantity > (jd.stock_quantity or 0):
                        raise StockError(f"{item.product.name} is out of stock.")
                else:
                    raise CartError("Invalid cart item.")

        # Handle address - either use existing or create snapshot
        selected_address_id = form_data.get('selected_address')
        use_new_address = form_data.get('use_new_address', False)
        
        if selected_address_id and not use_new_address:
            # Create snapshot of existing address
            try:
                existing_address = Address.objects.get(pk=selected_address_id, user=user, is_snapshot=False)
                address = Address.objects.create(
                    user=user,
                    full_name=existing_address.full_name,
                    phone=existing_address.phone,
                    email=existing_address.email,
                    address_line=existing_address.address_line,
                    city=existing_address.city,
                    state=existing_address.state,
                    pincode=existing_address.pincode,
                    is_snapshot=True,
                )
            except Address.DoesNotExist:
                raise CartError("Selected address not found.")
        else:
            # Create new snapshot address
            address = Address.objects.create(
                user=cart.user if cart.user else None,
                full_name=form_data["full_name"],
                phone=form_data["phone"],
                email=form_data.get("email", ""),
                address_line=form_data["address_line"],
                city=form_data["city"],
                state=form_data["state"],
                pincode=form_data["pincode"],
                is_snapshot=True,
            )

        totals = CartService.compute_totals(cart)
        order_number = cls._generate_order_number()
        order = Order.objects.create(
            user=cart.user if cart.user else None,
            order_number=order_number,
            subtotal=totals.subtotal,
            shipping=totals.shipping,
            total=totals.total,
            address=address,
        )

        for item in items:
            sellable = item.get_sellable()
            if sellable:
                if hasattr(sellable, "color_variant"):
                    snapshot = f"{sellable.size} {sellable.color_variant.name}".strip()
                else:
                    snapshot = f"{sellable.size} {getattr(sellable, 'color', '') or ''}".strip()
            else:
                if item.product.product_type == "jewellery":
                    jd = getattr(item.product, "jewellery_detail", None)
                    if jd:
                        purity = (jd.purity or "").strip()
                        snapshot = f"{jd.metal_type} {purity}".strip() if purity else jd.metal_type
                    else:
                        snapshot = item.product.name
                else:
                    snapshot = item.product.name

            OrderItem.objects.create(
                order=order,
                product=item.product,
                variant=item.variant,
                size_variant=item.size_variant,
                product_name=item.product.name,
                variant_snapshot=snapshot or item.product.name,
                unit_price=item.unit_price,
                quantity=item.quantity,
            )
            # Only reduce stock immediately for COD/WhatsApp payments
            # For Razorpay, stock will be reduced after successful payment verification
            if form_data.get("payment") != Payment.Method.RAZORPAY:
                if item.size_variant_id:
                    SizeVariant.objects.filter(pk=item.size_variant_id).update(
                        stock_quantity=F("stock_quantity") - item.quantity
                    )
                elif item.variant_id:
                    ProductVariant.objects.filter(pk=item.variant_id).update(
                        stock_quantity=F("stock_quantity") - item.quantity
                    )
                elif item.product.product_type == "jewellery":
                    from .models import JewelleryDetail
                    JewelleryDetail.objects.filter(product=item.product).update(
                        stock_quantity=F("stock_quantity") - item.quantity
                    )

        Payment.objects.create(
            order=order,
            method=form_data.get("payment", Payment.Method.COD),
            amount=totals.total,
        )

        # Only clear cart for COD/WhatsApp. For Razorpay, clear after payment verification
        if clear_cart:
            cart.status = Cart.Status.ORDERED
            cart.save(update_fields=["status"])
            cart.items.all().delete()

        # Send order notification email to admin/owner (non-blocking)
        send_order_notification_email_async(order)

        return order

