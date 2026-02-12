from django.conf import settings
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import IntegrityError, transaction
from django.db.models import Prefetch, Q, F, Sum, Count
from django.http import Http404, HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.views.generic import DetailView, FormView, ListView, TemplateView, View
from django.utils import timezone

import json
import razorpay
import hmac
import hashlib

import logging
logger = logging.getLogger(__name__)

from .auth_decorators import LoginRequiredForActionMixin
from .forms import CartAddForm, CartUpdateForm, CheckoutForm, ContactForm, NewsletterForm, ReviewForm
from .models import (
    Banner,
    CartItem,
    Category,
    ColorVariant,
    Order,
    OrderItem,
    Product,
    ProductVariant,
    Review,
    SizeVariant,
    Payment,
    Cart,
    Wishlist,
)
from .services import CartError, CartService, OrderService, StockError


def _active_color_variant_qs():
    """
    Base queryset for ColorVariant listings (collection & home JSON APIs).

    Rules:
    - ColorVariant is active
    - Parent product is active
    - At least one associated image
    - At least one in-stock SizeVariant (optional business rule: stock > 0)
    """
    try:
        return (
            ColorVariant.objects.filter(
                is_active=True,
                product__is_active=True,
                images__image__isnull=False,
                size_variants__is_active=True,
                size_variants__stock_quantity__gt=0,
            )
            .exclude(images__image="")
            .select_related("product", "product__category")
            .prefetch_related("images", "size_variants")
            .distinct()
        )
    except Exception as e:
        logger.error(f"Error building _active_color_variant_qs: {str(e)}", exc_info=True)
        return ColorVariant.objects.none()


class ProductListView(ListView):
    """
    Collection page.

    NOTE: This now lists ColorVariant rows instead of Products, treating each
    color as a standalone card while still using Product as the parent entity
    for name, price, rating, etc.
    """

    template_name = "category.html"
    context_object_name = "products"  # actually ColorVariant instances
    paginate_by = 12

    def get_queryset(self):
        try:
            qs = _active_color_variant_qs()

            category = self.request.GET.get("category")
            min_price = self.request.GET.get("min_price")
            max_price = self.request.GET.get("max_price")
            size = self.request.GET.get("size")
            material = self.request.GET.get("material")
            query = self.request.GET.get("q")

            if category and category != "all":
                qs = qs.filter(product__category__slug=category)
            if min_price:
                qs = qs.filter(product__price__gte=min_price)
            if max_price:
                qs = qs.filter(product__price__lte=max_price)
            if size:
                # Only variants that have this size in stock
                qs = qs.filter(
                    size_variants__size=size,
                    size_variants__is_active=True,
                    size_variants__stock_quantity__gt=0,
                )
            if material:
                qs = qs.filter(product__material__iexact=material.strip())
            if query:
                qs = qs.filter(
                    Q(product__name__icontains=query)
                    | Q(product__description__icontains=query)
                    | Q(product__category__name__icontains=query)
                )
            sort = (self.request.GET.get("sort") or "").strip().lower()
            if sort == "price_asc":
                qs = qs.order_by("product__price", "product__created_at")
            elif sort == "price_desc":
                qs = qs.order_by("-product__price", "-product__created_at")
            elif sort == "newest":
                qs = qs.order_by("-product__created_at", "display_order", "id")
            else:
                qs = qs.order_by("-product__created_at", "display_order", "id")
            return qs
        except Exception as e:
            logger.error(f"Error in ProductListView.get_queryset: {str(e)}", exc_info=True)
            return ColorVariant.objects.none()

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
            "material": self.request.GET.get("material", ""),
            "q": self.request.GET.get("q", ""),
            "sort": self.request.GET.get("sort", "newest"),
        }
        # Distinct non-empty material options for filter dropdown
        material_qs = (
            Product.objects.active()
            .exclude(material__isnull=True)
            .exclude(material__exact="")
            .values_list("material", flat=True)
            .distinct()
            .order_by("material")
        )
        context["material_options"] = list(material_qs)
        context["size_options"] = ["S", "M", "L", "XL", "XXL", "6M", "12M", "18M", "24M", "3Y"]
        context["sort_options"] = [
            ("newest", "Newest"),
            ("price_asc", "Price: Low to High"),
            ("price_desc", "Price: High to Low"),
        ]
        return context

    def get(self, request, *args, **kwargs):
        self.object_list = self.get_queryset()
        context = self.get_context_data()
        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return render(request, "partials/product_cards.html", context)
        return self.render_to_response(context)


class HomeView(TemplateView):
    template_name = "index.html"

    def get_context_data(self, **kwargs):
        try:
            context = super().get_context_data(**kwargs)
            context["categories"] = Category.objects.filter(is_active=True)
            variant_qs = ProductVariant.objects.filter(is_active=True, stock_quantity__gt=0).order_by("id")
            # Deal Of The Day products (admin-controlled flag + optional date window)
            today = timezone.now().date()
            deal_qs = (
                Product.objects.active()
                .filter(is_deal_of_day=True)
                .select_related("category")
                .prefetch_related(
                    Prefetch("variants", queryset=variant_qs),
                    "color_variants__images",
                    "color_variants__size_variants",
                )
            )
            deal_qs = deal_qs.filter(
                Q(deal_of_day_start__isnull=True) | Q(deal_of_day_start__lte=today),
                Q(deal_of_day_end__isnull=True) | Q(deal_of_day_end__gte=today),
            )[:8]
            context["deal_products"] = list(deal_qs)
            context["bestseller_products"] = (
                Product.objects.active()
                .filter(is_bestseller=True)
                .select_related("category")
                .prefetch_related(
                    Prefetch("variants", queryset=variant_qs),
                    "color_variants__images",
                    "color_variants__size_variants",
                )[:8]
            )
            active_banners = list(
                Banner.objects.filter(is_active=True).order_by("display_order", "created_at")
            )
            context["banners"] = [b for b in active_banners if b.image]
            context["active_page"] = "home"

            # --- Cart preview (home page) ---
            try:
                cart = CartService.get_or_create_cart(self.request)
                items_qs = cart.items.select_related(
                    "product",
                    "size_variant__color_variant__product",
                ).prefetch_related(
                    "size_variant__color_variant__images",
                )
                home_cart_items = list(items_qs)
                if home_cart_items:
                    totals = CartService.compute_totals(cart)
                    context["home_cart"] = cart
                    context["home_cart_items"] = home_cart_items
                    context["home_cart_totals"] = totals
                else:
                    context["home_cart_items"] = []
            except Exception as cart_exc:
                logger.error(f"Error building home cart preview: {cart_exc}", exc_info=True)
                context["home_cart_items"] = []

            # --- Wishlist variants (home page): variant-focused ---
            home_wishlist_variants = []
            user = getattr(self.request, "user", None)
            if user and user.is_authenticated:
                try:
                    wishlist_cv_ids = list(
                        Wishlist.objects.filter(user=user)
                        .filter(
                            color_variant__is_active=True,
                            color_variant__product__is_active=True,
                        )
                        .values_list("color_variant_id", flat=True)[:12]
                    )
                    if wishlist_cv_ids:
                        home_wishlist_variants = list(
                            _active_color_variant_qs()
                            .filter(pk__in=wishlist_cv_ids)
                            .order_by("display_order", "id")
                        )
                        # Preserve order from wishlist (most recent first)
                        order = {vid: i for i, vid in enumerate(wishlist_cv_ids)}
                        home_wishlist_variants.sort(key=lambda cv: order.get(cv.pk, 999))
                except Exception as wl_exc:
                    logger.error(f"Error building home wishlist variants: {wl_exc}", exc_info=True)
                    home_wishlist_variants = []
            context["home_wishlist_variants"] = home_wishlist_variants

            return context
        except Exception as e:
            logger.error(f"Error in HomeView.get_context_data: {str(e)}", exc_info=True)
            context = super().get_context_data(**kwargs)
            context["active_page"] = "home"
            context["featured_products"] = []
            context["bestseller_products"] = []
            context["categories"] = []
            context["banners"] = []
            return context


RECENTLY_VIEWED_MAX = 20
RECENTLY_VIEWED_VARIANTS_MAX = 20


def _update_recently_viewed(session, product_id):
    """Update session with product_id: FIFO queue, max RECENTLY_VIEWED_MAX, no duplicates."""
    if not product_id:
        return
    ids = list(session.get("recently_viewed_ids", []))
    try:
        pid = int(product_id)
    except (TypeError, ValueError):
        return
    if pid in ids:
        ids.remove(pid)
    ids.append(pid)
    ids = ids[-RECENTLY_VIEWED_MAX:]
    session["recently_viewed_ids"] = ids
    session.modified = True


def _update_recently_viewed_variant(session, color_variant_id):
    """
    Update session with ColorVariant ID: FIFO queue, max RECENTLY_VIEWED_VARIANTS_MAX, no duplicates.
    Used for variant-first recently viewed & recommendations on home page.
    """
    if not color_variant_id:
        return
    ids = list(session.get("recently_viewed_variant_ids", []))
    try:
        vid = int(color_variant_id)
    except (TypeError, ValueError):
        return
    if vid in ids:
        ids.remove(vid)
    ids.append(vid)
    ids = ids[-RECENTLY_VIEWED_VARIANTS_MAX:]
    session["recently_viewed_variant_ids"] = ids
    session.modified = True


class ProductDetailView(DetailView):
    template_name = "product.html"
    context_object_name = "product"
    slug_url_kwarg = "slug"

    def get(self, request, *args, **kwargs):
        self.object = self.get_object()
        _update_recently_viewed(request.session, self.object.pk)
        # Also track the selected ColorVariant for variant-first personalization on home.
        try:
            color_variants = list(self.object.color_variants.all()) if hasattr(self.object, "color_variants") else []
            selected_cv = self._select_color_variant(color_variants) if color_variants else None
            if selected_cv:
                _update_recently_viewed_variant(request.session, selected_cv.pk)
        except Exception as e:
            logger.error(f"Error updating recently viewed variants: {str(e)}", exc_info=True)
        return super().get(request, *args, **kwargs)

    def get_queryset(self):
        return (
            Product.objects.active()
            .select_related("category")
            .prefetch_related(
                Prefetch("variants", queryset=ProductVariant.objects.filter(is_active=True, stock_quantity__gt=0)),
                Prefetch(
                    "color_variants",
                    queryset=ColorVariant.objects.filter(is_active=True).prefetch_related(
                        "images",
                        "size_variants",
                    ).order_by("display_order", "name"),
                ),
            )
        )

    def _select_color_variant(self, color_variants):
        """
        Shared helper to choose which ColorVariant should be considered selected / focused.

        Priority:
        1) ?variant=<ColorVariant.id> that belongs to this product
        2) First color with any in‑stock SizeVariant
        3) Fallback to the first color variant
        """
        if not color_variants:
            return None

        selected_cv = None
        variant_param = self.request.GET.get("variant")
        if variant_param:
            try:
                vid = int(variant_param)
            except (TypeError, ValueError):
                vid = None
            if vid:
                for cv in color_variants:
                    if cv.id == vid:
                        selected_cv = cv
                        break

        if not selected_cv:
            # First color with any in‑stock size
            for cv in color_variants:
                for sv in cv.size_variants.all():
                    if getattr(sv, "is_active", True) and (sv.stock_quantity or 0) > 0:
                        selected_cv = cv
                        break
                if selected_cv:
                    break

        if not selected_cv and color_variants:
            selected_cv = color_variants[0]

        return selected_cv

    def get_context_data(self, **kwargs):
        try:
            context = super().get_context_data(**kwargs)
            product = context["product"]
            color_variants = list(product.color_variants.all()) if hasattr(product, "color_variants") else []

            if color_variants:
                selected_cv = self._select_color_variant(color_variants)

                if selected_cv:
                    # Reorder color_variants so the selected one is first. This ensures:
                    # - Its images are used in the main gallery by default
                    # - Its color swatch is pre-highlighted in the template/JS
                    color_variants.sort(key=lambda cv: 0 if cv.id == selected_cv.id else 1)

                # New flow: color-first, sizes per color
                context["color_variants"] = color_variants
                all_sizes = set()
                size_color_stock = {}
                color_sizes_stock = {}
                for cv in color_variants:
                    for sv in cv.size_variants.all():
                        if not getattr(sv, "is_active", True):
                            continue
                        all_sizes.add(sv.size)
                        if sv.size not in size_color_stock:
                            size_color_stock[sv.size] = {}
                        size_color_stock[sv.size][cv.name] = (sv.stock_quantity or 0) > 0
                        if cv.name not in color_sizes_stock:
                            color_sizes_stock[cv.name] = {}
                        color_sizes_stock[cv.name][sv.size] = {
                            "in_stock": (sv.stock_quantity or 0) > 0,
                            "size_variant_id": sv.id,
                        }
                context["sizes"] = sorted(all_sizes)
                context["colors"] = [cv.name for cv in color_variants]
                context["color_sizes_stock_json"] = json.dumps(color_sizes_stock)
                try:
                    context["size_color_stock_json"] = json.dumps(size_color_stock)
                except (TypeError, ValueError):
                    context["size_color_stock_json"] = json.dumps({})
                context["use_color_variants"] = True
            else:
                # Legacy flow: ProductVariant
                variants = list(product.variants.all())
                context["variants"] = variants
                context["color_variants"] = []
                context["sizes"] = sorted({v.size for v in variants})
                context["colors"] = sorted({v.color for v in variants if v.color})
                size_color_stock = {}
                for v in variants:
                    if v.size not in size_color_stock:
                        size_color_stock[v.size] = {}
                    color_key = v.color if v.color else "no_color"
                    size_color_stock[v.size][color_key] = (v.stock_quantity or 0) > 0
                try:
                    context["size_color_stock_json"] = json.dumps(size_color_stock)
                except (TypeError, ValueError):
                    context["size_color_stock_json"] = json.dumps({})
                context["color_sizes_stock_json"] = json.dumps({})
                context["use_color_variants"] = False

            # Related products
            context["related_products"] = (
                Product.objects.active()
                .filter(category=product.category)
                .exclude(pk=product.pk)
                .select_related("category")
                .prefetch_related("color_variants__images")[:4]
            )
            context["add_form"] = CartAddForm(initial={"product_id": product.id, "quantity": 1})
            context["active_page"] = "collection"
            # Wishlist is variant-focused: check if selected color variant is in wishlist
            selected_cv = context.get("color_variants") and context["color_variants"][0]
            context["in_wishlist"] = (
                Wishlist.objects.filter(
                    user=self.request.user, color_variant=selected_cv
                ).exists()
                if (self.request.user.is_authenticated and selected_cv)
                else False
            )
            context["selected_color_variant"] = selected_cv

            # ----- Ratings & Reviews (verified buyers only) -----
            reviews_qs = (
                Review.objects.filter(
                    product=product,
                    is_approved=True,
                    is_deleted=False,
                )
                .select_related("user", "order")
                .order_by("-created_at")
            )

            # Star breakdown (5★..1★)
            breakdown_raw = reviews_qs.values("rating").annotate(count=Count("id"))
            rating_breakdown = {i: 0 for i in range(5, 0, -1)}
            for row in breakdown_raw:
                r = int(row["rating"])
                if 1 <= r <= 5:
                    rating_breakdown[r] = row["count"]
            # Precomputed rows for template (star, count, percent)
            breakdown_rows = []
            total = product.total_reviews or 0
            for star in range(5, 0, -1):
                count = rating_breakdown.get(star, 0)
                percent = int((count / total) * 100) if total else 0
                breakdown_rows.append(
                    {
                        "star": star,
                        "count": count,
                        "percent": percent,
                    }
                )

            # Can current user write a review?
            can_review = False
            user_review = None
            if self.request.user.is_authenticated:
                user_review = Review.objects.filter(
                    product=product,
                    user=self.request.user,
                ).first()
                if not user_review:
                    has_delivered_order = OrderItem.objects.filter(
                        order__user=self.request.user,
                        order__status=Order.Status.DELIVERED,
                        product=product,
                    ).exists()
                    can_review = has_delivered_order

            context["reviews"] = list(reviews_qs)
            context["rating_breakdown"] = rating_breakdown
            context["rating_breakdown_rows"] = breakdown_rows
            context["can_review"] = can_review
            context["user_review"] = user_review
            context["review_form"] = ReviewForm()

            return context
        except Exception as e:
            logger.error(f"Error in ProductDetailView.get_context_data: {str(e)}", exc_info=True)
            raise


class ProductReviewCreateView(LoginRequiredForActionMixin, View):
    """
    AJAX-only endpoint to create a product review from a verified buyer.

    Business rules:
    - Only logged-in users.
    - User must have at least one delivered order for the product.
    - One review per (product, user).
    - Rating 1–5.
    - Uses transaction.atomic to avoid race conditions with uniqueness.
    """

    http_method_names = ["post"]

    def post(self, request, product_id: int, *args, **kwargs):
        is_ajax = request.headers.get("X-Requested-With") == "XMLHttpRequest"
        if not request.user.is_authenticated:
            login_url = f"{reverse('auth:login')}?next={request.build_absolute_uri()}"
            if is_ajax:
                return JsonResponse(
                    {
                        "success": False,
                        "login_required": True,
                        "login_url": login_url,
                        "error": "Login required to write a review.",
                    },
                    status=403,
                )
            return redirect(login_url)

        product = get_object_or_404(Product, pk=product_id, is_active=True)

        form = ReviewForm(request.POST)
        if not form.is_valid():
            if is_ajax:
                # Flatten errors
                error_text = "; ".join(
                    [f"{field}: {', '.join(errors)}" for field, errors in form.errors.items()]
                ) or "Invalid review data."
                return JsonResponse(
                    {"success": False, "error": error_text},
                    status=400,
                )
            messages.error(request, "Invalid review data.")
            return redirect("store:product_detail", slug=product.slug)

        # Verify delivered order for this user and product
        delivered_qs = (
            OrderItem.objects.select_related("order")
            .filter(
                order__user=request.user,
                order__status=Order.Status.DELIVERED,
                product=product,
            )
            .order_by("-order__created_at")
        )
        delivered_item = delivered_qs.first()
        if not delivered_item:
            msg = "You can only review products you have received (delivered orders only)."
            if is_ajax:
                return JsonResponse({"success": False, "error": msg}, status=403)
            messages.error(request, msg)
            return redirect("store:product_detail", slug=product.slug)

        # Prevent duplicate review
        if Review.objects.filter(product=product, user=request.user).exists():
            msg = "You have already reviewed this product."
            if is_ajax:
                return JsonResponse({"success": False, "error": msg}, status=400)
            messages.error(request, msg)
            return redirect("store:product_detail", slug=product.slug)

        try:
            with transaction.atomic():
                Review.objects.create(
                    product=product,
                    user=request.user,
                    order=delivered_item.order,
                    rating=form.cleaned_data["rating"],
                    title=form.cleaned_data.get("title", "").strip(),
                    comment=form.cleaned_data.get("comment", "").strip(),
                    # is_approved default is used; admin can later moderate
                )
        except IntegrityError:
            # Handles race conditions on unique (product, user)
            msg = "You have already reviewed this product."
            if is_ajax:
                return JsonResponse({"success": False, "error": msg}, status=400)
            messages.error(request, msg)
            return redirect("store:product_detail", slug=product.slug)
        except Exception as exc:
            logger.error("Error creating review: %s", exc, exc_info=True)
            msg = "Could not submit your review. Please try again."
            if is_ajax:
                return JsonResponse({"success": False, "error": msg}, status=500)
            messages.error(request, msg)
            return redirect("store:product_detail", slug=product.slug)

        success_msg = "Thank you for your review!"
        if is_ajax:
            return JsonResponse({"success": True, "message": success_msg})

        messages.success(request, success_msg)
        return redirect("store:product_detail", slug=product.slug)


def _normalize_image_url(url):
    """Ensure image URL is loadable: add https:// for host-only or protocol-relative URLs. Returns path or absolute URL."""
    if not url or not isinstance(url, str):
        return url
    url = url.strip()
    if url.startswith("http://") or url.startswith("https://"):
        return url
    if url.startswith("/"):
        base = getattr(settings, "MEDIA_URL", "/media/").rstrip("/")
        if base and url.startswith(base + "/") and "ytimg.com" in url:
            return "https://" + url[len(base) + 1:]
        return url
    return "https://" + url.lstrip("/")


class ProductColorImagesView(View):
    """AJAX: return image URLs for a color variant. Used for dynamic gallery on product page.
    Strict isolation: images are loaded only via color_variant.images (never product.images).
    When product_id is provided, the color variant must belong to that product.
    """

    def get(self, request, *args, **kwargs):
        color_variant_id = request.GET.get("color_variant_id")
        product_id = request.GET.get("product_id")
        if not color_variant_id:
            return JsonResponse({"images": []})
        try:
            qs = ColorVariant.objects.filter(pk=color_variant_id).prefetch_related("images")
            if product_id:
                qs = qs.filter(product_id=product_id)
            color_variant = qs.first()
        except (ValueError, TypeError):
            return JsonResponse({"images": []})
        if not color_variant:
            return JsonResponse({"images": []})
        images = []
        for img in color_variant.images.filter(image__isnull=False).exclude(image="").order_by("-is_primary", "id"):
            if img.image:
                try:
                    raw_url = img.image.url
                    url = _normalize_image_url(raw_url)
                    if url.startswith("/"):
                        url = request.build_absolute_uri(url)
                    images.append({
                        "url": url,
                        "is_primary": getattr(img, "is_primary", False),
                    })
                except Exception:
                    pass
        return JsonResponse({"images": images})


def _serialize_product_for_json(product, detail_url=None):
    """Build a dict for JSON API. Product should have category and color_variants__images prefetched."""
    if detail_url is None:
        detail_url = reverse("store:product_detail", args=[product.slug])
    card_images = getattr(product, "get_card_image_urls", lambda limit=20: [])(20)
    image_url = card_images[0] if card_images else "/static/images/banner.png"
    category_name = product.category.name if getattr(product, "category", None) else ""
    has_stock = False
    if hasattr(product, "variants"):
        for v in product.variants.all():
            if getattr(v, "is_active", True) and (getattr(v, "stock_quantity", 0) or 0) > 0:
                has_stock = True
                break
    if not has_stock and hasattr(product, "color_variants"):
        for cv in product.color_variants.all():
            for sv in cv.size_variants.all():
                if getattr(sv, "is_active", True) and (getattr(sv, "stock_quantity", 0) or 0) > 0:
                    has_stock = True
                    break
            if has_stock:
                break
    discount = 0
    if getattr(product, "original_price", None) and product.original_price and product.price:
        if product.original_price > product.price:
            discount = round(((float(product.original_price) - float(product.price)) / float(product.original_price)) * 100)
    avg_rating = getattr(product, "average_rating", None)
    if avg_rating is not None:
        avg_rating = float(avg_rating)
    total_reviews = getattr(product, "total_reviews", None)
    if total_reviews is not None:
        total_reviews = int(total_reviews)
    return {
        "id": product.id,
        "name": product.name or "",
        "slug": product.slug or "",
        "price": str(product.price),
        "original_price": str(product.original_price) if product.original_price else None,
        "discount_percent": discount,
        "url": detail_url,
        "image_url": image_url,
        "card_images": card_images,
        "category_name": category_name or "",
        "has_stock": has_stock,
        "average_rating": avg_rating,
        "total_reviews": total_reviews,
    }


def _serialize_color_variant_for_json(color_variant, detail_url=None):
    """
    Build a dict for JSON APIs where each card represents ONE ColorVariant.

    - Primary image & card images come strictly from this ColorVariant.images
    - Pricing & rating come from the parent Product
    - URL encodes the selected variant via query param, keeping canonical product URL
    """
    product = getattr(color_variant, "product", None)
    if not product:
        return {}

    if detail_url is None:
        base = reverse("store:product_detail", args=[product.slug])
        detail_url = f"{base}?variant={color_variant.id}"

    # Images: do not mix between variants
    images_qs = getattr(color_variant, "images", None)
    card_images = []
    if images_qs is not None:
        for img in images_qs.all():
            if getattr(img, "image", None):
                try:
                    raw_url = img.image.url
                except Exception:
                    continue
                url = _normalize_image_url(raw_url)
                if url:
                    card_images.append(url)

    image_url = card_images[0] if card_images else "/static/images/banner.png"

    # Stock > 0 rule at variant level
    has_stock = False
    is_low_stock = False
    size_variants = getattr(color_variant, "size_variants", None)
    if size_variants is not None:
        for sv in size_variants.all():
            qty = sv.stock_quantity or 0
            if getattr(sv, "is_active", True) and qty > 0:
                has_stock = True
                if qty <= 5:
                    is_low_stock = True
                break

    discount = 0
    if getattr(product, "original_price", None) and product.original_price and product.price:
        if product.original_price > product.price:
            discount = round(
                ((float(product.original_price) - float(product.price)) / float(product.original_price)) * 100
            )

    avg_rating = getattr(product, "average_rating", None)
    if avg_rating is not None:
        avg_rating = float(avg_rating)
    total_reviews = getattr(product, "total_reviews", None)
    if total_reviews is not None:
        total_reviews = int(total_reviews)

    category_name = ""
    if getattr(product, "category", None):
        category_name = product.category.name or ""

    return {
        "id": product.id,
        "variant_id": color_variant.id,
        "name": product.name or "",
        "slug": product.slug or "",
        "color_name": getattr(color_variant, "name", "") or "",
        "price": str(product.price),
        "original_price": str(product.original_price) if product.original_price else None,
        "discount_percent": discount,
        "url": detail_url,
        "image_url": image_url,
        "card_images": card_images,
        "category_name": category_name,
        "has_stock": has_stock,
        "is_low_stock": is_low_stock,
        "average_rating": avg_rating,
        "total_reviews": total_reviews,
    }


class NewArrivalsView(View):
    """JSON API: latest active products. ?limit=30 default (capped at 30)."""

    def get(self, request):
        try:
            limit = request.GET.get("limit", "30")
            try:
                limit = min(max(int(limit), 1), 30)
            except (TypeError, ValueError):
                limit = 30

            qs = (
                _active_color_variant_qs()
                .order_by("-product__created_at", "display_order", "id")[:limit]
            )
            variants = list(qs)
            payload = [_serialize_color_variant_for_json(cv) for cv in variants]
            return JsonResponse({"products": payload})
        except Exception as e:
            logger.exception("NewArrivalsView: %s", e)
            return JsonResponse({"products": []})


class TopSellingView(View):
    """JSON API: top selling products from non-cancelled orders (placed/confirmed/shipped/delivered/paid).
    Includes COD and other methods; not limited to payment.status=PAID."""

    def get(self, request):
        try:
            limit = request.GET.get("limit", "8")
            try:
                limit = min(max(int(limit), 1), 24)
            except (TypeError, ValueError):
                limit = 8
            # Non-cancelled orders only (so COD, WhatsApp, and paid all count)
            order_filter = ~Q(order__status=Order.Status.CANCELLED)
            product_ids_with_qty = (
                OrderItem.objects.filter(order_filter)
                .values("product_id")
                .annotate(total_sold=Sum("quantity"))
                .filter(total_sold__gt=0, product__is_active=True)
                .order_by("-total_sold")[:limit]
            )
            ids_ordered = [x["product_id"] for x in product_ids_with_qty]
            if not ids_ordered:
                return JsonResponse({"products": []})
            preserved_order = dict((pk, i) for i, pk in enumerate(ids_ordered))

            # Start from all active color variants for these products, then
            # sort by product popularity + display order and trim to `limit`.
            qs = _active_color_variant_qs().filter(product_id__in=ids_ordered)
            variants = sorted(
                list(qs),
                key=lambda cv: (
                    preserved_order.get(getattr(cv.product, "pk", None), 999),
                    getattr(cv, "display_order", 0),
                    cv.id,
                ),
            )[:limit]
            payload = [_serialize_color_variant_for_json(cv) for cv in variants]
            return JsonResponse({"products": payload})
        except Exception as e:
            logger.exception("TopSellingView: %s", e)
            return JsonResponse({"products": []})


class RecentlyViewedView(View):
    """JSON API: ColorVariants from session recently_viewed_variant_ids (FIFO, max 20)."""

    def get(self, request):
        try:
            raw_ids = list(request.session.get("recently_viewed_variant_ids", []))
            if not raw_ids:
                return JsonResponse({"products": []})
            seen = set()
            unique_ids = []
            for pk in raw_ids:
                try:
                    pk_int = int(pk)
                except (TypeError, ValueError):
                    continue
                if pk_int in seen:
                    continue
                seen.add(pk_int)
                unique_ids.append(pk_int)
            ids = unique_ids[-RECENTLY_VIEWED_VARIANTS_MAX:]
            if not ids:
                return JsonResponse({"products": []})
            preserved_order = dict((pk, i) for i, pk in enumerate(ids))
            qs = _active_color_variant_qs().filter(pk__in=ids)
            variants = sorted(list(qs), key=lambda cv: preserved_order.get(cv.pk, 999))
            payload = [_serialize_color_variant_for_json(cv) for cv in variants]
            return JsonResponse({"products": payload})
        except Exception as e:
            logger.exception("RecentlyViewedView: %s", e)
            return JsonResponse({"products": []})


class YouMayLikeView(View):
    """JSON API: ColorVariant recommendations based on recently viewed variants.

    For each recently viewed variant:
    - Recommend other ColorVariants of the same parent Product
    - Exclude the variants that were actually viewed
    """

    def get(self, request):
        try:
            raw_ids = list(request.session.get("recently_viewed_variant_ids", []))
            if not raw_ids:
                return JsonResponse({"products": []})

            seen = set()
            variant_ids = []
            for val in raw_ids:
                try:
                    vid = int(val)
                except (TypeError, ValueError):
                    continue
                if vid in seen:
                    continue
                seen.add(vid)
                variant_ids.append(vid)

            if not variant_ids:
                return JsonResponse({"products": []})

            viewed_variants = list(_active_color_variant_qs().filter(pk__in=variant_ids))
            if not viewed_variants:
                return JsonResponse({"products": []})

            viewed_variant_ids = {cv.pk for cv in viewed_variants}
            product_ids = {getattr(cv, "product_id", None) for cv in viewed_variants}
            product_ids.discard(None)
            if not product_ids:
                return JsonResponse({"products": []})

            base_qs = (
                _active_color_variant_qs()
                .filter(product_id__in=product_ids)
                .exclude(pk__in=viewed_variant_ids)
            )

            limit = 16
            candidates = list(
                base_qs.order_by("product__name", "display_order", "id")[:limit]
            )
            if not candidates:
                return JsonResponse({"products": []})

            payload = [_serialize_color_variant_for_json(cv) for cv in candidates]
            return JsonResponse({"products": payload})
        except Exception as e:
            logger.exception("YouMayLikeView: %s", e)
            return JsonResponse({"products": []})


class WishlistToggleView(View):
    """POST: toggle color variant in wishlist. Login required; returns JSON. Guest → login_required + login_url."""

    def post(self, request):
        is_ajax = request.headers.get("X-Requested-With") == "XMLHttpRequest"
        if not request.user.is_authenticated:
            if is_ajax:
                next_url = request.GET.get("next") or request.build_absolute_uri()
                login_url = f"{reverse('auth:login')}?next={next_url}"
                return JsonResponse(
                    {"success": False, "login_required": True, "login_url": login_url},
                    status=403,
                )
            return redirect(f"{reverse('auth:login')}?next={request.build_absolute_uri()}")

        color_variant_id = None
        if request.content_type and "application/json" in request.content_type:
            try:
                data = json.loads(request.body)
                color_variant_id = data.get("color_variant_id")
            except (json.JSONDecodeError, TypeError):
                pass
        if color_variant_id is None:
            color_variant_id = request.POST.get("color_variant_id")
        try:
            color_variant_id = int(color_variant_id)
        except (TypeError, ValueError):
            return JsonResponse({"success": False, "error": "Invalid variant"}, status=400)

        color_variant = (
            ColorVariant.objects.filter(
                pk=color_variant_id,
                is_active=True,
                product__is_active=True,
            )
            .select_related("product")
            .first()
        )
        if not color_variant:
            return JsonResponse({"success": False, "error": "Variant not found"}, status=404)

        wishlist, created = Wishlist.objects.get_or_create(
            user=request.user, color_variant=color_variant
        )
        if not created:
            wishlist.delete()
            added = False
        else:
            added = True
        count = Wishlist.objects.filter(user=request.user).count()
        return JsonResponse({"success": True, "added": added, "count": count})


class WishlistIdsView(View):
    """GET: return list of wishlist color variant IDs for current user (for marking hearts)."""

    def get(self, request):
        if not request.user.is_authenticated:
            return JsonResponse({"variant_ids": []})
        try:
            ids = list(
                Wishlist.objects.filter(user=request.user)
                .filter(color_variant__is_active=True, color_variant__product__is_active=True)
                .values_list("color_variant_id", flat=True)
            )
            return JsonResponse({"variant_ids": ids})
        except Exception as e:
            logger.exception("WishlistIdsView: %s", e)
            return JsonResponse({"variant_ids": []})


class WishlistPageView(LoginRequiredForActionMixin, TemplateView):
    """Wishlist page: list of saved color variants. Invalid/deleted excluded."""

    template_name = "wishlist.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if not self.request.user.is_authenticated:
            context["wishlist_items"] = []
            return context
        items = (
            Wishlist.objects.filter(
                user=self.request.user,
                color_variant__is_active=True,
                color_variant__product__is_active=True,
            )
            .select_related("color_variant__product", "color_variant__product__category")
            .prefetch_related("color_variant__images")
            .order_by("-created_at")
        )
        context["wishlist_items"] = list(items)
        context["active_page"] = "wishlist"
        return context


class CartView(LoginRequiredForActionMixin, TemplateView):
    template_name = "cart.html"

    def get_context_data(self, **kwargs):
        try:
            context = super().get_context_data(**kwargs)
            cart = CartService.get_or_create_cart(self.request)
            items = cart.items.select_related(
                "product", "variant", "size_variant",
                "size_variant__color_variant",
            ).prefetch_related(
                "product__color_variants__images",
                "size_variant__color_variant__images",
            ).all()
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
        except Exception as e:
            logger.error(f"Error in CartView.get_context_data: {str(e)}", exc_info=True)
            context = super().get_context_data(**kwargs)
            context.update({
                "cart": None,
                "items": [],
                "totals": {"subtotal": 0, "shipping": 0, "total": 0},
                "update_form": CartUpdateForm(),
                "active_page": "cart",
            })
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
        sellable = None

        if data.get("size_variant_id"):
            size_variant = SizeVariant.objects.filter(
                color_variant__product=product,
                pk=data["size_variant_id"],
                is_active=True,
                stock_quantity__gt=0,
            ).select_related("color_variant").first()
            if size_variant:
                sellable = size_variant
            if not sellable:
                messages.error(request, "Selected variant is unavailable.")
                if is_ajax:
                    return JsonResponse({"success": False, "error": "Selected variant is unavailable."}, status=400)
                return redirect("store:product_detail", slug=product.slug)
        else:
            size = data.get("size") or ""
            if not size:
                messages.error(request, "Please select a size.")
                if is_ajax:
                    return JsonResponse({"success": False, "error": "Please select a size."}, status=400)
                return redirect("store:product_detail", slug=product.slug)
            size_has_instock_colors = ProductVariant.objects.filter(
                product=product,
                size=size,
                is_active=True,
                stock_quantity__gt=0,
            ).exclude(color__in=(None, "")).exists()
            if size_has_instock_colors and not (data.get("color") or "").strip():
                messages.error(request, "Please select a color.")
                if is_ajax:
                    return JsonResponse({"success": False, "error": "Please select a color."}, status=400)
                return redirect("store:product_detail", slug=product.slug)
            variant = ProductVariant.objects.filter(
                product=product,
                size=size,
                color=data.get("color") or "",
                is_active=True,
                stock_quantity__gt=0,
            ).first()
            if variant:
                sellable = variant
            if not sellable:
                messages.error(request, "Selected variant is unavailable.")
                if is_ajax:
                    return JsonResponse({"success": False, "error": "Selected variant is unavailable."}, status=400)
                return redirect("store:product_detail", slug=product.slug)

        cart = CartService.get_or_create_cart(request)
        try:
            CartService.add_item(cart, sellable, data["quantity"])
        except StockError as exc:
            messages.error(request, str(exc))
            if is_ajax:
                return JsonResponse({"success": False, "error": str(exc)}, status=400)
        else:
            if is_ajax:
                cart_count = sum(item.quantity for item in cart.items.all())
                return JsonResponse({"success": True, "cart_count": cart_count})
        action = request.POST.get("action", "add")
        if action == "buy":
            return redirect("store:checkout")
        if action == "whatsapp":
            return redirect(f"{reverse_lazy('store:checkout')}?payment=whatsapp")
        # Add ?added=1 to cart redirect for notification
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
        try:
            cart = CartService.get_or_create_cart(request)
            item = get_object_or_404(CartItem, pk=kwargs.get("item_id"), cart=cart)
            item.delete()
            messages.success(request, "Item removed.")
        except Exception as e:
            logger.error(f"Error in RemoveCartItemView: {str(e)}", exc_info=True)
            messages.error(request, "Failed to remove item from cart.")
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
        try:
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
                    "items": cart.items.select_related(
                        "product", "variant", "size_variant",
                        "size_variant__color_variant",
                    ).prefetch_related(
                        "product__color_variants__images",
                        "size_variant__color_variant__images",
                    ),
                    "totals": totals,
                    "form": CheckoutForm(initial=initial, user=self.request.user),
                    "addresses": addresses,
                    "default_address": default_address,
                    "active_page": "cart",
                }
            )
            return context
        except Exception as e:
            logger.error(f"Error in CheckoutView.get_context_data: {str(e)}", exc_info=True)
            context = super().get_context_data(**kwargs)
            context.update({
                "cart": None,
                "items": [],
                "totals": {"subtotal": 0, "shipping": 0, "total": 0},
                "form": CheckoutForm(user=self.request.user),
                "addresses": [],
                "default_address": None,
                "active_page": "cart",
            })
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
            "items": cart.items.select_related(
                "product", "variant", "size_variant",
                "size_variant__color_variant",
            ).prefetch_related(
                "product__color_variants__images",
                "size_variant__color_variant__images",
            ),
            "totals": totals,
            "addresses": addresses,
            "default_address": default_address,
            "active_page": "cart",
        })
        return context

    def form_valid(self, form):
        cart = CartService.get_or_create_cart(self.request)
        payment_method = form.cleaned_data.get("payment")
        
        # For Razorpay, don't create order yet - only create after payment verification
        if payment_method == "razorpay":
            # Store form data in session for later order creation
            self.request.session["pending_checkout_data"] = form.cleaned_data
            
            # Validate cart and stock before payment
            try:
                items = (
                    cart.items.select_related("variant", "size_variant", "product")
                    .select_for_update(of=("self",))
                    .all()
                )
                if not items:
                    raise CartError("Cart is empty.")
                for item in items:
                    sellable = item.get_sellable()
                    if not sellable:
                        raise CartError("Invalid cart item.")
                    if item.quantity > sellable.stock_quantity:
                        raise StockError(f"{item.product.name} is out of stock.")
            except (CartError, StockError) as exc:
                messages.error(self.request, str(exc))
                return redirect("store:checkout")
            
            # Create a temporary order placeholder for payment (we'll finalize after payment)
            # For Razorpay, don't clear cart yet - only clear after payment verification
            try:
                order = OrderService.create_order(cart, form.cleaned_data, self.request.user, clear_cart=False)
                # Mark order as pending payment
                order.status = Order.Status.PLACED  # Will be confirmed only after payment
                order.save(update_fields=['status'])
            except (CartError, StockError) as exc:
                messages.error(self.request, str(exc))
                return redirect("store:checkout")
            
            self.request.session["last_order_number"] = order.order_number
            # Redirect to payment page for Razorpay
            return redirect("store:razorpay_payment", order_number=order.order_number)
        
        # For COD and WhatsApp, create order immediately and clear cart
        try:
            order = OrderService.create_order(cart, form.cleaned_data, self.request.user, clear_cart=True)
        except (CartError, StockError) as exc:
            messages.error(self.request, str(exc))
            return redirect("store:checkout")
        self.request.session["last_order_number"] = order.order_number
        
        if payment_method == "whatsapp":
            messages.info(self.request, "We will contact you on WhatsApp to confirm your order.")
        return redirect("store:order_success", order_number=order.order_number)

    def form_invalid(self, form):
        return self.render_to_response(self.get_context_data(form=form))


class OrderSuccessView(DetailView):
    template_name = "success.html"
    context_object_name = "order"
    slug_url_kwarg = "order_number"
    slug_field = "order_number"

    def get_queryset(self):
        return Order.objects.select_related("address", "payment").prefetch_related("items")

    def dispatch(self, request, *args, **kwargs):
        try:
            order_number = kwargs.get("order_number")
            order = get_object_or_404(Order, order_number=order_number)
            if request.user.is_authenticated:
                if order.user and order.user != request.user:
                    return HttpResponseForbidden()
            else:
                if request.session.get("last_order_number") != order_number:
                    return HttpResponseForbidden()
            return super().dispatch(request, *args, **kwargs)
        except Http404:
            logger.warning(f"Order not found: {order_number}")
            raise
        except Exception as e:
            logger.error(f"Error in OrderSuccessView.dispatch: {str(e)}", exc_info=True)
            messages.error(request, "Failed to retrieve order details.")
            return redirect("store:home")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["active_page"] = "orders"
        return context


class OrderHistoryView(LoginRequiredMixin, ListView):
    template_name = "orders.html"
    context_object_name = "orders"
    paginate_by = 10

    def get_queryset(self):
        try:
            return (
                Order.objects.filter(user=self.request.user)
                .select_related("address")
                .prefetch_related("items")
            )
        except Exception as e:
            logger.error(f"Error in OrderHistoryView.get_queryset: {str(e)}", exc_info=True)
            return Order.objects.none()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["active_page"] = "orders"
        return context


class ContactView(FormView):
    template_name = "contact.html"
    form_class = ContactForm
    success_url = reverse_lazy("store:contact")

    def form_valid(self, form):
        try:
            form.save()
            messages.success(self.request, "Thanks for reaching out! We will respond soon.")
        except Exception as e:
            logger.error(f"Error in ContactView.form_valid: {str(e)}", exc_info=True)
            messages.error(self.request, "Failed to save your message. Please try again.")
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
        try:
            email = form.cleaned_data["email"].lower()
            subscription, created = form._meta.model.objects.get_or_create(email=email)
            if not created and not subscription.is_active:
                subscription.is_active = True
                subscription.save(update_fields=["is_active"])
            messages.success(self.request, "Thanks for subscribing!")
        except Exception as e:
            logger.error(f"Error in NewsletterSubscribeView.form_valid: {str(e)}", exc_info=True)
            messages.error(self.request, "Failed to subscribe. Please try again.")
        return super().form_valid(form)

    def form_invalid(self, form):
        messages.error(self.request, "Please enter a valid email.")
        return redirect(self.get_success_url())

class RazorpayPaymentView(LoginRequiredForActionMixin, View):
    """Handle Razorpay payment initialization"""
    
    def post(self, request, *args, **kwargs):
        try:
            import logging
            logger = logging.getLogger(__name__)
            
            order_number = request.POST.get('order_number')
            logger.info(f"POST request for order: {order_number}")
            
            order = Order.objects.select_related('address', 'user').get(order_number=order_number)
            logger.info(f"Order found: {order.order_number}, User: {order.user}")
            
            # Check authorization
            if order.user != request.user:
                logger.warning(f"Unauthorized access attempt for order {order_number}")
                return JsonResponse({'status': 'error', 'message': 'Unauthorized'}, status=403)
            
            # Get or create payment
            payment, created = Payment.objects.get_or_create(
                order=order,
                defaults={
                    'method': Payment.Method.RAZORPAY,
                    'amount': order.total,
                    'status': Payment.Status.PENDING
                }
            )
            
            # Initialize Razorpay client
            client = razorpay.Client(auth=(settings.RZP_CLIENT_ID, settings.RZP_CLIENT_SECRET))
            
            # Create Razorpay order
            razorpay_order = client.order.create({
                'amount': int(order.total * 100), 
                'currency': 'INR',
                'payment_capture': 1 
            })
            
            # Store Razorpay order ID
            payment.razorpay_order_id = razorpay_order['id']
            payment.save(update_fields=['razorpay_order_id'])
            
            return JsonResponse({
                'status': 'success',
                'razorpay_order_id': razorpay_order['id'],
                'razorpay_key_id': settings.RZP_CLIENT_ID,
                'amount': int(order.total * 100),
                'order_number': order.order_number,
                'customer_name': order.address.full_name,
                'customer_email': order.address.email or request.user.email,
                'customer_phone': order.address.phone,
            })
        except Order.DoesNotExist:
            logger = logging.getLogger(__name__)
            logger.error(f"Order not found: {order_number}")
            return JsonResponse({'status': 'error', 'message': 'Order not found'}, status=404)
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Payment initialization error: {str(e)}", exc_info=True)
            return JsonResponse({'status': 'error', 'message': str(e)}, status=500)
    
    def get(self, request, *args, **kwargs):
        """Display payment page"""
        try:
            order_number = kwargs.get('order_number')
            order = Order.objects.select_related('address', 'user').get(order_number=order_number)
            
            # Check authorization
            if order.user != request.user:
                return HttpResponseForbidden()
            
            context = {
                'order': order,
                'razorpay_key_id': settings.RZP_CLIENT_ID,
            }
            return self.render_to_response(context)
        except Order.DoesNotExist:
            return redirect('store:checkout')
    
    def render_to_response(self, context):
        from django.shortcuts import render
        return render(self.request, 'razorpay_payment.html', context)



class RazorpayPaymentVerifyView(LoginRequiredForActionMixin, View):
    """Verify Razorpay payment signature"""
    
    def post(self, request, *args, **kwargs):
        try:
            logger = logging.getLogger(__name__)
            
            data = json.loads(request.body)
            
            razorpay_order_id = data.get('razorpay_order_id')
            razorpay_payment_id = data.get('razorpay_payment_id')
            razorpay_signature = data.get('razorpay_signature')
            
            logger.info(f"Payment verification attempt - Order: {razorpay_order_id}, Payment: {razorpay_payment_id}")
            
            payment = Payment.objects.select_related('order').get(
                razorpay_order_id=razorpay_order_id
            )
            
            # Verify signature
            signature_data = f"{razorpay_order_id}|{razorpay_payment_id}"
            signature_check = hmac.new(
                settings.RZP_CLIENT_SECRET.encode(),
                signature_data.encode(),
                hashlib.sha256
            ).hexdigest()
            
            if signature_check == razorpay_signature:
                # Payment successful - update payment fields
                payment.razorpay_payment_id = razorpay_payment_id
                payment.razorpay_signature = razorpay_signature
                payment.status = Payment.Status.PAID
                payment.processed_at = timezone.now()
                payment.save(update_fields=['status', 'processed_at', 'razorpay_payment_id', 'razorpay_signature'])
                
                # Now reduce stock after successful payment
                order = payment.order
                for item in order.items.all():
                    if item.size_variant_id:
                        SizeVariant.objects.filter(pk=item.size_variant_id).update(
                            stock_quantity=F("stock_quantity") - item.quantity
                        )
                    elif item.variant_id:
                        ProductVariant.objects.filter(pk=item.variant_id).update(
                            stock_quantity=F("stock_quantity") - item.quantity
                        )
                
                # Clear cart after successful payment
                cart = CartService.get_or_create_cart(request)
                if cart.items.exists():
                    cart.status = Cart.Status.ORDERED
                    cart.save(update_fields=["status"])
                    cart.items.all().delete()
                
                # Clear pending checkout data from session
                if "pending_checkout_data" in request.session:
                    del request.session["pending_checkout_data"]
                
                return JsonResponse({
                    'status': 'success',
                    'message': 'Payment verified successfully',
                    'order_number': payment.order.order_number
                })
            else:
                # Payment signature verification failed
                payment.status = Payment.Status.FAILED
                payment.save(update_fields=['status'])
                
                # Delete the order since payment failed (no stock was reduced)
                order = payment.order
                order_number = order.order_number
                order.delete()  # This will cascade delete the payment and order items
                
                # Clear pending checkout data from session
                if "pending_checkout_data" in request.session:
                    del request.session["pending_checkout_data"]
                
                return JsonResponse({
                    'status': 'error',
                    'message': 'Payment verification failed. Please try again.',
                    'redirect': '/cart/'
                }, status=400)
        except Payment.DoesNotExist:
            # Clear pending checkout data from session
            if "pending_checkout_data" in request.session:
                del request.session["pending_checkout_data"]
            
            return JsonResponse({
                'status': 'error',
                'message': 'Payment record not found',
                'redirect': '/cart/'
            }, status=404)
        except Exception as e:
            # Clear pending checkout data from session
            if "pending_checkout_data" in request.session:
                del request.session["pending_checkout_data"]
            
            return JsonResponse({
                'status': 'error',
                'message': f'Payment verification error: {str(e)}',
                'redirect': '/cart/'
            }, status=500)


class RazorpayPaymentCancelView(LoginRequiredForActionMixin, View):
    """Handle Razorpay payment cancellation (user closes payment modal)"""
    
    def post(self, request, *args, **kwargs):
        try:
            data = json.loads(request.body)
            order_number = data.get('order_number')
            
            # Get the order
            order = Order.objects.select_related('user', 'address').get(order_number=order_number)
            
            # Check authorization
            if order.user != request.user:
                logger.warning(f"Unauthorized access attempt for order {order_number}")
                return JsonResponse({'status': 'error', 'message': 'Unauthorized'}, status=403)
            
            # Get payment record
            try:
                payment = order.payment
            except Payment.DoesNotExist:
                payment = None
            
            # Delete the order (cascade deletes payment and items)
            order.delete()
            
            # Clear pending checkout data from session
            if "pending_checkout_data" in request.session:
                del request.session["pending_checkout_data"]
            
            return JsonResponse({
                'status': 'success',
                'message': 'Payment cancelled. Your order has been cancelled.',
                'redirect': '/cart/'
            })
        except Order.DoesNotExist:
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"Order not found for cancellation: {order_number}")
            
            # Clear pending checkout data from session
            if "pending_checkout_data" in request.session:
                del request.session["pending_checkout_data"]
            
            return JsonResponse({
                'status': 'success',
                'message': 'Returning to cart...',
                'redirect': '/cart/'
            })
        except Exception as e:
            # Clear pending checkout data from session
            if "pending_checkout_data" in request.session:
                del request.session["pending_checkout_data"]
            
            return JsonResponse({
                'status': 'success',
                'message': 'Returning to cart...',
                'redirect': '/cart/'
            })