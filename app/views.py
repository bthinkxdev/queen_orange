from django.conf import settings
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Prefetch, Q
from django.http import Http404, HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse, reverse_lazy
from django.views.generic import DetailView, FormView, ListView, TemplateView, View
from django.utils import timezone

import json
import razorpay
import hmac
import hashlib

from .auth_decorators import LoginRequiredForActionMixin
from .forms import CartAddForm, CartUpdateForm, CheckoutForm, ContactForm, NewsletterForm
from .models import CartItem, Category, Order, Product, ProductImage, ProductVariant, Payment
from .services import CartError, CartService, OrderService, StockError

import logging
logger = logging.getLogger(__name__)

class ProductListView(ListView):
    template_name = "category.html"
    context_object_name = "products"
    paginate_by = 24

    def get_queryset(self):
        qs = Product.objects.active().select_related("category")
        
        category = self.request.GET.get("category")
        min_price = self.request.GET.get("min_price")
        max_price = self.request.GET.get("max_price")
        size = self.request.GET.get("size")
        query = self.request.GET.get("q")
        material = self.request.GET.get("material")
        plating = self.request.GET.get("plating")
        occasion = self.request.GET.get("occasion")
        style = self.request.GET.get("style")
        finish = self.request.GET.get("finish")
        sort_by = self.request.GET.get("sort", "newest")

        if category and category != "all":
            qs = qs.filter(category__slug=category)
        if min_price:
            qs = qs.filter(price__gte=min_price)
        if max_price:
            qs = qs.filter(price__lte=max_price)
        if size:
            qs = qs.filter(variants__size=size, variants__is_active=True, variants__stock_quantity__gt=0)
        if material:
            qs = qs.filter(material__icontains=material)
        if plating:
            qs = qs.filter(plating_type__icontains=plating)
        if occasion:
            qs = qs.filter(occasion__icontains=occasion)
        if style:
            qs = qs.filter(style__icontains=style)
        if finish:
            qs = qs.filter(finish__icontains=finish)
        if query:
            qs = qs.filter(
                Q(name__icontains=query)
                | Q(description__icontains=query)
                | Q(category__name__icontains=query)
                | Q(variants__sku__icontains=query)
            )
        

        # Sorting
        if sort_by == "price_low":
            qs = qs.order_by("price")
        elif sort_by == "price_high":
            qs = qs.order_by("-price")
        elif sort_by == "newest":
            qs = qs.order_by("-created_at")
        elif sort_by == "popular":
            qs = qs.filter(is_bestseller=True).order_by("-created_at")
        
        # Apply distinct then prefetch_related for images
        return qs.distinct().prefetch_related("images")


    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["categories"] = Category.objects.filter(is_active=True)
        context["page_title"] = "Shop All Jewelry"
        context["active_page"] = "collection"
        
        category_slug = self.request.GET.get("category")
        selected_category = None
        if category_slug and category_slug != "all":
            selected_category = Category.objects.filter(slug=category_slug).first()
            if selected_category:
                context["page_title"] = selected_category.name
        
        context["selected_category"] = selected_category
        context["filters"] = {
            "category": self.request.GET.get("category", "all"),
            "min_price": self.request.GET.get("min_price", ""),
            "max_price": self.request.GET.get("max_price", ""),
            "size": self.request.GET.get("size", ""),
            "q": self.request.GET.get("q", ""),
            "material": self.request.GET.get("material", ""),
            "plating": self.request.GET.get("plating", ""),
            "occasion": self.request.GET.get("occasion", ""),
            "style": self.request.GET.get("style", ""),
            "finish": self.request.GET.get("finish", ""),
            "sort": self.request.GET.get("sort", "newest"),
        }
        
        # Category-aware size options
        # context["size_config"] = self.get_size_config(category_slug)
        
        # Get dynamic filter options from existing products
        active_products = Product.objects.filter(is_active=True)
        
        # Helper function to get unique options (removes duplicates and normalizes)
        def get_unique_options(queryset, field_name):
            values = queryset.values_list(field_name, flat=True).distinct()
            unique_dict = {}
            for val in values:
                if val and isinstance(val, str):
                    normalized = val.strip()
                    if normalized:
                        unique_dict[normalized.lower()] = normalized
            return sorted(unique_dict.values())
        
        # Filter options
        context["material_options"] = get_unique_options(active_products, 'material')
        context["plating_options"] = get_unique_options(active_products, 'plating_type')
        context["finish_options"] = get_unique_options(active_products, 'finish')
        context["occasion_options"] = get_unique_options(active_products, 'occasion')
        context["style_options"] = get_unique_options(active_products, 'style')
        
        return context
    
    def get_size_config(self, category_slug):
        """Return category-specific size configuration"""
        if not category_slug or category_slug == "all":
            return {"type": "none", "label": "Size", "options": []}
        
        category_lower = category_slug.lower()
        
        if "bangle" in category_lower or "kada" in category_lower:
            return {
                "type": "bangle",
                "label": "Bangle Size (Diameter)",
                "options": ["2.2", "2.4", "2.6", "2.8", "2.10", "Adjustable"]
            }
        elif "ring" in category_lower:
            return {
                "type": "ring",
                "label": "Ring Size",
                "options": ["6", "7", "8", "9", "10", "11", "12", "Adjustable"]
            }
        elif "chain" in category_lower:
            return {
                "type": "chain",
                "label": "Chain Length",
                "options": ["16 inches", "18 inches", "20 inches", "22 inches", "24 inches"]
            }
        elif "necklace" in category_lower:
            return {
                "type": "necklace",
                "label": "Necklace Length",
                "options": ["Choker", "Short", "Medium", "Long"]
            }
        elif "earring" in category_lower:
            return {
                "type": "earring",
                "label": "Earring Type",
                "options": ["Studs", "Drops", "Hoops", "Chandbali", "Jhumka"]
            }
        else:
            return {
                "type": "none",
                "label": "Size",
                "options": ["Free Size", "Adjustable"]
            }


class HomeView(TemplateView):
    template_name = "index.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["categories"] = Category.objects.filter(is_active=True)
        variant_qs = ProductVariant.objects.filter(is_active=True, stock_quantity__gt=0).order_by("id")
        image_qs = ProductImage.objects.order_by("-is_primary", "id")
        context["featured_products"] = (
            Product.objects.active()
            .filter(is_featured=True)
            .select_related("category")
            .prefetch_related(
                Prefetch("images", queryset=image_qs),
                Prefetch("variants", queryset=variant_qs)
            )[:8]
        )
        context["bestseller_products"] = (
            Product.objects.active()
            .filter(is_bestseller=True)
            .select_related("category")
            .prefetch_related(
                Prefetch("images", queryset=image_qs),
                Prefetch("variants", queryset=variant_qs)
            )[:8]
        )
        context["new_arrivals_products"] = (
            Product.objects.active()
            .order_by("-created_at")
            .select_related("category")
            .prefetch_related(
                Prefetch("images", queryset=image_qs),
                Prefetch("variants", queryset=variant_qs)
            )[:20]
        )
        context["active_page"] = "home"
        return context


class ProductDetailView(DetailView):
    template_name = "product.html"
    context_object_name = "product"
    slug_url_kwarg = "slug"

    def get_queryset(self):
        return (
            Product.objects.active()
            .select_related("category")
            .prefetch_related(
                Prefetch("images", queryset=ProductImage.objects.order_by("-is_primary", "id")),
                Prefetch("variants", queryset=ProductVariant.objects.filter(is_active=True, stock_quantity__gt=0)),
            )
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        product = context["product"]
        variants = list(product.variants.all())
        context["variants"] = variants
        context["has_variants"] = len(variants) > 0
        context["sizes"] = sorted({variant.size for variant in variants if variant.size})
        context["colors"] = sorted({variant.color for variant in variants if variant.color})
        context["related_products"] = (
            Product.objects.active()
            .filter(category=product.category)
            .exclude(pk=product.pk)
            .select_related("category")[:4]
        )
        context["add_form"] = CartAddForm(initial={"product_id": product.id, "quantity": 1})
        context["active_page"] = "collection"
        return context


class CartView(LoginRequiredForActionMixin, TemplateView):
    template_name = "cart.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        cart = CartService.get_or_create_cart(self.request)
        items = cart.items.select_related("product", "variant").prefetch_related("product__images").all()
        totals = CartService.compute_totals(cart)
        context.update(
            {
                "cart": cart,
                "items": items,
                "totals": totals,
                "update_form": CartUpdateForm(),
                "active_page": "cart",
            }
        )
        return context


class AddToCartView(LoginRequiredForActionMixin, View):
    http_method_names = ["post"]

    def post(self, request, *args, **kwargs):
        is_ajax = request.headers.get("x-requested-with") == "XMLHttpRequest"
        form = CartAddForm(request.POST)
        if not form.is_valid():
            err_msg = "Invalid cart data."
            if form.errors:
                first_errors = [str(e) for err_list in form.errors.values() for e in err_list]
                if first_errors:
                    err_msg = first_errors[0]
            messages.error(request, err_msg)
            if is_ajax:
                return JsonResponse({"success": False, "error": err_msg}, status=400)
            product_id = request.POST.get("product_id")
            if product_id and Product.objects.filter(pk=product_id).exists():
                product = Product.objects.get(pk=product_id)
                return redirect("store:product_detail", slug=product.slug)
            return redirect("store:cart")
        data = form.cleaned_data
        product = get_object_or_404(Product, pk=data["product_id"])
        if ProductVariant.objects.filter(product=product, color__isnull=False).exclude(color="").exists():
            if not data.get("color"):
                messages.error(request, "Please select a color.")
                if is_ajax:
                    return JsonResponse({"success": False, "error": "Please select a color."}, status=400)
                return redirect("store:product_detail", slug=product.slug)
        size_value = data.get("size") or ""
        color_value = data.get("color") or ""

        if not size_value:
            variant = ProductVariant.objects.filter(
                product=product,
                is_active=True,
                stock_quantity__gt=0,
            ).first()
        else:
            variant = ProductVariant.objects.filter(
                product=product,
                size=size_value,
                color=color_value,
                is_active=True,
                stock_quantity__gt=0,
            ).first()

        if not variant:
            messages.error(request, "Selected variant is unavailable.")
            if is_ajax:
                return JsonResponse({"success": False, "error": "Selected variant is unavailable."}, status=400)
            return redirect("store:product_detail", slug=product.slug)
        cart = CartService.get_or_create_cart(request)
        try:
            CartService.add_item(cart, variant, data["quantity"])
        except StockError as exc:
            messages.error(request, str(exc))
            if is_ajax:
                return JsonResponse({"success": False, "error": str(exc)}, status=400)
        else:
            # messages.success(request, "Added to cart.")
            if is_ajax:
                cart_count = sum(item.quantity for item in cart.items.all())
                payload = {"success": True, "cart_count": cart_count}
                action = request.POST.get("action", "add")
                if action == "buy":
                    payload["redirect"] = reverse("store:checkout")
                return JsonResponse(payload)
        action = request.POST.get("action", "add")
        if action == "buy":
            return redirect("store:checkout")
        url = reverse("store:cart") + "?added=1"
        return redirect(url)


class UpdateCartItemView(LoginRequiredForActionMixin, View):
    http_method_names = ["post"]

    def post(self, request, *args, **kwargs):
        form = CartUpdateForm(request.POST)
        if not form.is_valid():
            messages.error(request, "Invalid update.")
            return redirect("store:cart")
        cart = CartService.get_or_create_cart(request)
        item = get_object_or_404(CartItem, pk=form.cleaned_data["item_id"], cart=cart)
        try:
            CartService.update_item(item, form.cleaned_data["quantity"])
        except StockError as exc:
            messages.error(request, str(exc))
        return redirect("store:cart")


class RemoveCartItemView(LoginRequiredForActionMixin, View):
    http_method_names = ["post"]

    def post(self, request, *args, **kwargs):
        cart = CartService.get_or_create_cart(request)
        item = get_object_or_404(CartItem, pk=kwargs.get("item_id"), cart=cart)
        item.delete()
        messages.success(request, "Item removed.")
        return redirect("store:cart")


class CheckoutView(LoginRequiredForActionMixin, TemplateView):
    template_name = "checkout.html"

    def dispatch(self, request, *args, **kwargs):
        # Check authentication first
        if not request.user.is_authenticated:
            next_url = request.get_full_path()
            login_url = f"{reverse('auth:login')}?next={next_url}"
            return redirect(login_url)
        
        cart = CartService.get_or_create_cart(request)
        if not cart.items.exists():
            messages.info(request, "Your cart is empty.")
            return redirect("store:cart")
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        cart = CartService.get_or_create_cart(self.request)
        totals = CartService.compute_totals(cart)
        
        # Get user's saved addresses
        from .models import Address
        addresses = Address.objects.filter(
            user=self.request.user,
            is_snapshot=False
        ).order_by('-is_default', '-created_at')
        
        # Get default address
        default_address = addresses.filter(is_default=True).first()
        
        # Prepare initial form data
        initial = {}
        if default_address:
            initial['selected_address'] = default_address.id
        
        context.update(
            {
                "cart": cart,
                "items": cart.items.select_related("product", "variant").prefetch_related("product__images"),
                "totals": totals,
                "form": CheckoutForm(initial=initial, user=self.request.user),
                "addresses": addresses,
                "default_address": default_address,
                "active_page": "cart",
            }
        )
        return context


class OrderCreateView(LoginRequiredForActionMixin, FormView):
    form_class = CheckoutForm
    template_name = "checkout.html"

    def dispatch(self, request, *args, **kwargs):
        # Check authentication first
        if not request.user.is_authenticated:
            next_url = reverse('store:checkout')
            login_url = f"{reverse('auth:login')}?next={next_url}"
            return redirect(login_url)
        
        cart = CartService.get_or_create_cart(request)
        if not cart.items.exists():
            messages.info(request, "Your cart is empty.")
            return redirect("store:cart")
        return super().dispatch(request, *args, **kwargs)
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        cart = CartService.get_or_create_cart(self.request)
        totals = CartService.compute_totals(cart)
        
        # Get user's saved addresses
        from .models import Address
        addresses = Address.objects.filter(
            user=self.request.user,
            is_snapshot=False
        ).order_by('-is_default', '-created_at')
        
        default_address = addresses.filter(is_default=True).first()
        
        context.update({
            "cart": cart,
            "items": cart.items.select_related("product", "variant").prefetch_related("product__images"),
            "totals": totals,
            "addresses": addresses,
            "default_address": default_address,
            "active_page": "cart",
        })
        return context

    def form_valid(self, form):
        cart = CartService.get_or_create_cart(self.request)
        try:
            order = OrderService.create_order(cart, form.cleaned_data, self.request.user)
        except (CartError, StockError) as exc:
            messages.error(self.request, str(exc))
            return redirect("store:checkout")
        self.request.session["last_order_number"] = order.order_number
        payment_method = form.cleaned_data.get("payment")
        if payment_method == "razorpay":
            return redirect("store:razorpay_payment", order_number=order.order_number)
        if payment_method == "whatsapp":
            messages.info(self.request, "We will contact you on WhatsApp to confirm your order.")
        return redirect("store:order_success", order_number=order.order_number)

    def form_invalid(self, form):
        messages.error(self.request, "Please correct the errors in the form.")
        return self.render_to_response(self.get_context_data(form=form))


class OrderSuccessView(DetailView):
    template_name = "success.html"
    context_object_name = "order"
    slug_url_kwarg = "order_number"
    slug_field = "order_number"

    def get_queryset(self):
        return Order.objects.select_related("address").prefetch_related("items")

    def dispatch(self, request, *args, **kwargs):
        order_number = kwargs.get("order_number")
        order = get_object_or_404(Order, order_number=order_number)
        if request.user.is_authenticated:
            if order.user and order.user != request.user:
                return HttpResponseForbidden()
        else:
            if request.session.get("last_order_number") != order_number:
                return HttpResponseForbidden()
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["active_page"] = "orders"
        return context


class OrderHistoryView(LoginRequiredMixin, ListView):
    template_name = "orders.html"
    context_object_name = "orders"
    paginate_by = 10

    def get_queryset(self):
        return (
            Order.objects.filter(user=self.request.user)
            .select_related("address")
            .prefetch_related("items__product")
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["active_page"] = "orders"
        return context


class ContactView(FormView):
    template_name = "contact.html"
    form_class = ContactForm
    success_url = reverse_lazy("store:contact")

    def form_valid(self, form):
        form.save()
        messages.success(self.request, "Thanks for reaching out! We will respond soon.")
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["active_page"] = "contact"
        return context


class StaticPageView(TemplateView):
    template_name = "about.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if self.extra_context and "active_page" in self.extra_context:
            context["active_page"] = self.extra_context["active_page"]
        return context


class NewsletterSubscribeView(FormView):
    form_class = NewsletterForm
    success_url = reverse_lazy("store:home")

    def get_success_url(self):
        return self.request.META.get("HTTP_REFERER", str(self.success_url))

    def form_valid(self, form):
        email = form.cleaned_data["email"].lower()
        subscription, created = form._meta.model.objects.get_or_create(email=email)
        if not created and not subscription.is_active:
            subscription.is_active = True
            subscription.save(update_fields=["is_active"])
        messages.success(self.request, "Thanks for subscribing!")
        return super().form_valid(form)

    def form_invalid(self, form):
        messages.error(self.request, "Please enter a valid email.")
        return redirect(self.get_success_url())

def _can_access_order(request, order):
    """Allow access if order belongs to user or guest session matches."""
    if order.user is None:
        return request.session.get("last_order_number") == order.order_number
    return request.user.is_authenticated and order.user == request.user


class RazorpayPaymentView(View):
    """Handle Razorpay payment initialization."""

    def get(self, request, *args, **kwargs):
        try:
            order_number = kwargs.get('order_number')
            order = Order.objects.select_related('address', 'user').get(order_number=order_number)
            if not _can_access_order(request, order):
                return HttpResponseForbidden()
            context = {'order': order, 'razorpay_key_id': settings.RZP_CLIENT_ID}
            from django.shortcuts import render
            return render(request, 'razorpay_payment.html', context)
        except Order.DoesNotExist:
            return redirect('store:checkout')

    def post(self, request, *args, **kwargs):
        try:
            order_number = request.POST.get('order_number')
            if not order_number or not str(order_number).strip():
                return JsonResponse({'status': 'error', 'message': 'Order number required'}, status=400)
            order_number = str(order_number).strip()
            order = Order.objects.select_related('address', 'user').get(order_number=order_number)
            if not _can_access_order(request, order):
                return JsonResponse({'status': 'error', 'message': 'Unauthorized'}, status=403)
            payment, created = Payment.objects.get_or_create(
                order=order,
                defaults={
                    'method': Payment.Method.RAZORPAY,
                    'amount': order.total,
                    'status': Payment.Status.PENDING
                }
            )
            client = razorpay.Client(auth=(settings.RZP_CLIENT_ID, settings.RZP_CLIENT_SECRET))
            base_url = request.build_absolute_uri('/').rstrip('/')
            if not settings.DEBUG:
                base_url = base_url.replace('http://', 'https://')

            razorpay_order = client.order.create({
                'amount': int(order.total * 100),
                'currency': 'INR',
                'payment_capture': 1,
            })

            payment.razorpay_order_id = razorpay_order['id']
            payment.save(update_fields=['razorpay_order_id'])

            customer_email = order.address.email or (getattr(request.user, 'email', '') or '')

            return JsonResponse({
                'status': 'success',
                'razorpay_order_id': razorpay_order['id'],
                'razorpay_key_id': settings.RZP_CLIENT_ID,
                'amount': int(order.total * 100),
                'order_number': order.order_number,
                'customer_name': order.address.full_name,
                'customer_email': customer_email,
                'customer_phone': order.address.phone,
                'callback_url': f"{base_url}/payment/razorpay/callback/?order={order.order_number}",  # ← new
            })
        except Order.DoesNotExist:
            return JsonResponse({'status': 'error', 'message': 'Order not found'}, status=404)
        except Exception as e:
            logger.error("Payment initialization error: %s", e, exc_info=True)
            return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


class RazorpayPaymentVerifyView(View):
    """Verify Razorpay payment signature."""

    def post(self, request, *args, **kwargs):
        try:
            if not request.body:
                return JsonResponse({'status': 'error', 'message': 'Request body required'}, status=400)
            try:
                data = json.loads(request.body)
            except json.JSONDecodeError:
                return JsonResponse({'status': 'error', 'message': 'Invalid JSON'}, status=400)

            razorpay_order_id = data.get('razorpay_order_id') or ''
            razorpay_payment_id = data.get('razorpay_payment_id') or ''
            razorpay_signature = data.get('razorpay_signature') or ''

            if not razorpay_order_id or not razorpay_payment_id or not razorpay_signature:
                return JsonResponse({'status': 'error', 'message': 'Missing payment verification data'}, status=400)

            payment = Payment.objects.select_related('order').get(razorpay_order_id=razorpay_order_id)

            signature_data = f"{razorpay_order_id}|{razorpay_payment_id}"
            signature_check = hmac.new(
                settings.RZP_CLIENT_SECRET.encode(),
                signature_data.encode(),
                hashlib.sha256
            ).hexdigest()

            if signature_check == razorpay_signature:
                if payment.status != Payment.Status.PAID:
                    payment.razorpay_payment_id = razorpay_payment_id
                    payment.razorpay_signature = razorpay_signature
                    payment.status = Payment.Status.PAID
                    payment.processed_at = timezone.now()
                    payment.save(update_fields=[
                        'status', 'processed_at', 'razorpay_payment_id', 'razorpay_signature'
                    ])
                return JsonResponse({
                    'status': 'success',
                    'message': 'Payment verified successfully',
                    'order_number': payment.order.order_number
                })

            payment.status = Payment.Status.FAILED
            payment.save(update_fields=['status'])
            return JsonResponse({'status': 'error', 'message': 'Payment verification failed'}, status=400)

        except Payment.DoesNotExist:
            return JsonResponse({'status': 'error', 'message': 'Payment record not found'}, status=404)
        except Exception as e:
            logger.error("Payment verification error: %s", e, exc_info=True)
            return JsonResponse({'status': 'error', 'message': str(e)}, status=500)
        
class RazorpayCallbackView(View):
    """
    Handles UPI intent return — works for success, failure AND dismiss.
    Razorpay may send GET or POST depending on the scenario.
    """

    def get(self, request, *args, **kwargs):
        return self.handle(request, request.GET)

    def post(self, request, *args, **kwargs):
        return self.handle(request, request.POST)

    def handle(self, request, data):
        try:
            razorpay_payment_id = data.get('razorpay_payment_id', '')
            razorpay_order_id   = data.get('razorpay_order_id', '')
            razorpay_signature  = data.get('razorpay_signature', '')

            # Fallback order number from URL param (set by us for dismiss case)
            fallback_order_number = request.GET.get('order', '')

            # ── No payment ID = dismissed or failed ──
            if not razorpay_payment_id:
                error_reason = (
                    data.get('error[description]')
                    or data.get('error_description')
                    or 'Payment cancelled'
                )
                logger.warning("UPI callback — no payment: %s", error_reason)

                # Try razorpay_order_id first
                if razorpay_order_id:
                    try:
                        payment = Payment.objects.select_related('order').get(
                            razorpay_order_id=razorpay_order_id
                        )
                        if payment.status == Payment.Status.PENDING:
                            payment.status = Payment.Status.FAILED
                            payment.save(update_fields=['status'])
                        return redirect(
                            reverse('store:razorpay_payment',
                                    kwargs={'order_number': payment.order.order_number})
                        )
                    except Payment.DoesNotExist:
                        pass

                # Fallback — use order number from URL param
                if fallback_order_number:
                    return redirect(
                        reverse('store:razorpay_payment',
                                kwargs={'order_number': fallback_order_number})
                    )

                return redirect('store:cart')

            # ── Signature verification ──
            signature_data  = f"{razorpay_order_id}|{razorpay_payment_id}"
            signature_check = hmac.new(
                settings.RZP_CLIENT_SECRET.encode(),
                signature_data.encode(),
                hashlib.sha256
            ).hexdigest()

            payment = Payment.objects.select_related('order').get(
                razorpay_order_id=razorpay_order_id
            )

            if signature_check == razorpay_signature:
                if payment.status != Payment.Status.PAID:
                    payment.razorpay_payment_id = razorpay_payment_id
                    payment.razorpay_signature  = razorpay_signature
                    payment.status              = Payment.Status.PAID
                    payment.processed_at        = timezone.now()
                    payment.save(update_fields=[
                        'status', 'processed_at',
                        'razorpay_payment_id', 'razorpay_signature'
                    ])
                    logger.info("UPI callback success: %s", razorpay_payment_id)

                # ── Set session so OrderSuccessView allows access ──
                request.session['last_order_number'] = payment.order.order_number

                return redirect(
                    reverse('store:order_success',
                            kwargs={'order_number': payment.order.order_number})
                )

            payment.status = Payment.Status.FAILED
            payment.save(update_fields=['status'])
            logger.warning("UPI callback — signature mismatch: %s", razorpay_order_id)
            return redirect(
                reverse('store:razorpay_payment',
                        kwargs={'order_number': payment.order.order_number})
            )

        except Payment.DoesNotExist:
            logger.error("UPI callback — payment not found")
            if fallback_order_number:
                return redirect(
                    reverse('store:razorpay_payment',
                            kwargs={'order_number': fallback_order_number})
                )
            return redirect('store:cart')
        except Exception as e:
            logger.error("UPI callback error: %s", e, exc_info=True)
            return redirect('store:cart')