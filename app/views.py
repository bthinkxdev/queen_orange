from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Prefetch, Q
from django.http import Http404, HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse, reverse_lazy
from django.views.generic import DetailView, FormView, ListView, TemplateView, View

from .auth_decorators import LoginRequiredForActionMixin
from .forms import CartAddForm, CartUpdateForm, CheckoutForm, ContactForm, NewsletterForm
from .models import CartItem, Category, Order, Product, ProductImage, ProductVariant
from .services import CartError, CartService, OrderService, StockError


class ProductListView(ListView):
    template_name = "category.html"
    context_object_name = "products"
    paginate_by = 24

    def get_queryset(self):
        qs = (
            Product.objects.active()
            .select_related("category")
            .prefetch_related(
                Prefetch("images", queryset=ProductImage.objects.order_by("-is_primary", "id"))
            )
        )
        category = self.request.GET.get("category")
        min_price = self.request.GET.get("min_price")
        max_price = self.request.GET.get("max_price")
        size = self.request.GET.get("size")
        query = self.request.GET.get("q")

        if category and category != "all":
            qs = qs.filter(category__slug=category)
        if min_price:
            qs = qs.filter(price__gte=min_price)
        if max_price:
            qs = qs.filter(price__lte=max_price)
        if size:
            qs = qs.filter(variants__size=size, variants__is_active=True, variants__stock_quantity__gt=0)
        if query:
            qs = qs.filter(
                Q(name__icontains=query)
                | Q(description__icontains=query)
                | Q(category__name__icontains=query)
            )
        return qs.distinct()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["categories"] = Category.objects.filter(is_active=True)
        context["page_title"] = "Shop All Products"
        context["active_page"] = "collection"
        category_slug = self.request.GET.get("category")
        if category_slug and category_slug != "all":
            category = Category.objects.filter(slug=category_slug).first()
            if category:
                context["page_title"] = category.name
        context["filters"] = {
            "category": self.request.GET.get("category", "all"),
            "min_price": self.request.GET.get("min_price", ""),
            "max_price": self.request.GET.get("max_price", ""),
            "size": self.request.GET.get("size", ""),
            "q": self.request.GET.get("q", ""),
        }
        context["size_options"] = ["S", "M", "L", "XL", "XXL", "6M", "12M", "18M", "24M", "3Y"]
        return context


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
        context["sizes"] = sorted({variant.size for variant in variants})
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
            messages.error(request, "Invalid cart data.")
            if is_ajax:
                return JsonResponse({"success": False, "error": "Invalid cart data."}, status=400)
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
        variant = ProductVariant.objects.filter(
            product=product,
            size=data["size"],
            color=data.get("color", ""),
            is_active=True,
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
            messages.success(request, "Added to cart.")
            if is_ajax:
                cart_count = sum(item.quantity for item in cart.items.all())
                return JsonResponse({"success": True, "cart_count": cart_count})
        action = request.POST.get("action", "add")
        if action == "buy":
            return redirect("store:checkout")
        if action == "whatsapp":
            return redirect(f"{reverse_lazy('store:checkout')}?payment=whatsapp")
        return redirect("store:cart")


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
        payment_method = self.request.GET.get("payment")
        if payment_method not in {"cod", "whatsapp"}:
            payment_method = None
        
        initial = {"payment": payment_method} if payment_method else {}
        
        # If default address exists, pre-select it
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
        if form.cleaned_data.get("payment") == "whatsapp":
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
            .prefetch_related("items")
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
