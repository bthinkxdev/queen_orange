import json
import logging
import time
from datetime import timedelta

from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.mixins import UserPassesTestMixin
from django.contrib.auth.decorators import user_passes_test
from django.db import connection, transaction
from django.db.models import Count, Max, Sum, Q, F, ProtectedError
from django.db.models.functions import TruncDate
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.views.generic import (
    CreateView,
    DeleteView,
    DetailView,
    ListView,
    TemplateView,
    UpdateView,
    View,
)

from .models import (
    Banner,
    CartItem,
    Category,
    ColorVariant,
    ColorVariantImage,
    ContactMessage,
    JewelleryDetail,
    Order,
    OrderItem,
    Product,
    ProductVariant,
    Review,
    SizeVariant,
)
from django.conf import settings

from .admin_forms import (
    AdminLoginForm,
    BannerForm,
    CategoryForm,
    JewelleryImageFormSetEdit,
    ProductBasicEditForm,
    STANDARD_SIZES,
    _validate_image_file,
)
from .utils.debug_trace import Trace
from .admin_product_edit_views import (
    ProductCreateBasicView as BaseProductCreateBasicView,
    ProductEditView as BaseProductEditView,
    ProductUpdateBasicView as BaseProductUpdateBasicView,
    ProductToggleActiveView as BaseProductToggleActiveView,
    ProductVariantsListApiView as BaseProductVariantsListApiView,
    ProductVariantAddApiView as BaseProductVariantAddApiView,
    VariantUpdateApiView as BaseVariantUpdateApiView,
    VariantDeleteApiView as BaseVariantDeleteApiView,
    VariantAddSizeApiView as BaseVariantAddSizeApiView,
    SizeVariantUpdateStockView as BaseSizeVariantUpdateStockView,
    VariantUploadImageView as BaseVariantUploadImageView,
    ProductImageDeleteView as BaseProductImageDeleteView,
    ProductImageReplaceView as BaseProductImageReplaceView,
    ProductJewelleryDetailApiView as BaseProductJewelleryDetailApiView,
    JewelleryUploadImageView as BaseJewelleryUploadImageView,
    JewelleryImageDeleteView as BaseJewelleryImageDeleteView,
    JewelleryImageReplaceView as BaseJewelleryImageReplaceView,
)

logger = logging.getLogger(__name__)


class StaffRequiredMixin(UserPassesTestMixin):
    """Mixin to require staff/admin access"""
    
    def test_func(self):
        return self.request.user.is_authenticated and self.request.user.is_staff
    
    def handle_no_permission(self):
        if not self.request.user.is_authenticated:
            return redirect("admin_panel:login")
        messages.error(self.request, "You don't have permission to access this area.")
        return redirect("store:home")


# Product edit modular API (wrappers with StaffRequiredMixin)
class ProductCreateBasicView(StaffRequiredMixin, BaseProductCreateBasicView):
    """POST create-basic/ — staff only."""


class ProductEditView(StaffRequiredMixin, BaseProductEditView):
    pass


class ProductUpdateBasicView(StaffRequiredMixin, BaseProductUpdateBasicView):
    pass


class ProductToggleActiveView(StaffRequiredMixin, BaseProductToggleActiveView):
    pass


class ProductVariantsListApiView(StaffRequiredMixin, BaseProductVariantsListApiView):
    pass


class ProductVariantAddApiView(StaffRequiredMixin, BaseProductVariantAddApiView):
    pass


class VariantUpdateApiView(StaffRequiredMixin, BaseVariantUpdateApiView):
    pass


class VariantDeleteApiView(StaffRequiredMixin, BaseVariantDeleteApiView):
    pass


class VariantAddSizeApiView(StaffRequiredMixin, BaseVariantAddSizeApiView):
    pass


class SizeVariantUpdateStockView(StaffRequiredMixin, BaseSizeVariantUpdateStockView):
    pass


class VariantUploadImageView(StaffRequiredMixin, BaseVariantUploadImageView):
    pass


class ProductImageDeleteView(StaffRequiredMixin, BaseProductImageDeleteView):
    pass


class ProductImageReplaceView(StaffRequiredMixin, BaseProductImageReplaceView):
    pass


class ProductJewelleryDetailApiView(StaffRequiredMixin, BaseProductJewelleryDetailApiView):
    pass


class JewelleryUploadImageView(StaffRequiredMixin, BaseJewelleryUploadImageView):
    pass


class JewelleryImageDeleteView(StaffRequiredMixin, BaseJewelleryImageDeleteView):
    pass


class JewelleryImageReplaceView(StaffRequiredMixin, BaseJewelleryImageReplaceView):
    pass


# Authentication Views
class AdminLoginView(View):
    template_name = "admin/login.html"
    
    def get(self, request):
        if request.user.is_authenticated and request.user.is_staff:
            return redirect("admin_panel:dashboard")
        form = AdminLoginForm()
        return render(request, self.template_name, {"form": form})
    
    def post(self, request):
        form = AdminLoginForm(request.POST)
        if form.is_valid():
            username = form.cleaned_data["username"]
            password = form.cleaned_data["password"]
            user = authenticate(request, username=username, password=password)
            
            if user and user.is_staff:
                login(request, user)
                messages.success(request, f"Welcome back, {user.username}!")
                return redirect("admin_panel:dashboard")
            else:
                messages.error(request, "Invalid credentials or insufficient permissions.")
        
        return render(request, self.template_name, {"form": form})


class AdminLogoutView(View):
    def post(self, request):
        logout(request)
        messages.success(request, "Logged out successfully.")
        return redirect("admin_panel:login")


# Dashboard View
class AdminDashboardView(StaffRequiredMixin, TemplateView):
    template_name = "admin/dashboard.html"
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Date filters
        today = timezone.now().date()
        last_7_days = today - timedelta(days=7)
        last_30_days = today - timedelta(days=30)
        
        # Order statistics
        total_orders = Order.objects.count()
        orders_today = Order.objects.filter(created_at__date=today).count()
        orders_this_week = Order.objects.filter(created_at__date__gte=last_7_days).count()
        orders_this_month = Order.objects.filter(created_at__date__gte=last_30_days).count()
        
        # Revenue statistics
        total_revenue = Order.objects.aggregate(total=Sum("total"))["total"] or 0
        revenue_today = Order.objects.filter(created_at__date=today).aggregate(total=Sum("total"))["total"] or 0
        revenue_this_week = Order.objects.filter(created_at__date__gte=last_7_days).aggregate(total=Sum("total"))["total"] or 0
        revenue_this_month = Order.objects.filter(created_at__date__gte=last_30_days).aggregate(total=Sum("total"))["total"] or 0
        
        # Order status breakdown
        order_status = Order.objects.values("status").annotate(count=Count("id"))
        
        # Product statistics
        total_products = Product.objects.filter(is_active=True).count()
        low_stock_products = ProductVariant.objects.filter(
            is_active=True,
            stock_quantity__lte=5,
            stock_quantity__gt=0
        ).count()
        out_of_stock_products = ProductVariant.objects.filter(
            is_active=True,
            stock_quantity=0
        ).count()
        
        # Recent orders
        recent_orders = Order.objects.select_related("address").order_by("-created_at")[:10]
        
        # Top selling products (last 30 days): sum quantities from non-cancelled orders only
        top_rows = list(
            OrderItem.objects.filter(
                order__created_at__gte=last_30_days,
            )
            .exclude(order__status=Order.Status.CANCELLED)
            .values("product_id")
            .annotate(
                total_sold=Sum("quantity"),
                revenue=Sum(F("quantity") * F("unit_price")),
            )
            .order_by("-total_sold")[:5]
        )
        if top_rows:
            product_ids = [r["product_id"] for r in top_rows]
            products_by_id = {p.pk: p for p in Product.objects.filter(pk__in=product_ids)}
            top_products = []
            for r in top_rows:
                p = products_by_id.get(r["product_id"])
                if p:
                    top_products.append(
                        type("TopProductRow", (), {
                            "name": p.name,
                            "total_sold": r["total_sold"],
                            "revenue": r["revenue"] or 0,
                        })()
                    )
        else:
            top_products = []
        
        # Recent messages
        unresolved_messages = ContactMessage.objects.filter(is_resolved=False).count()
        
        # Daily revenue chart data (last 14 days)
        import json
        chart_data = []
        for i in range(13, -1, -1):
            date = today - timedelta(days=i)
            daily_revenue = Order.objects.filter(
                created_at__date=date
            ).aggregate(total=Sum("total"))["total"] or 0
            chart_data.append({
                "date": date.strftime("%d %b"),
                "revenue": float(daily_revenue)
            })
        chart_data_json = json.dumps(chart_data)
        
        context.update({
            "total_orders": total_orders,
            "orders_today": orders_today,
            "orders_this_week": orders_this_week,
            "orders_this_month": orders_this_month,
            "total_revenue": total_revenue,
            "revenue_today": revenue_today,
            "revenue_this_week": revenue_this_week,
            "revenue_this_month": revenue_this_month,
            "order_status": order_status,
            "total_products": total_products,
            "low_stock_products": low_stock_products,
            "out_of_stock_products": out_of_stock_products,
            "recent_orders": recent_orders,
            "top_products": top_products,
            "unresolved_messages": unresolved_messages,
            "chart_data": chart_data_json,
            "active_menu": "dashboard",
        })
        
        return context


# Category Management Views
class CategoryListView(StaffRequiredMixin, ListView):
    model = Category
    template_name = "admin/category_list.html"
    context_object_name = "categories"
    paginate_by = 20
    
    def get_queryset(self):
        qs = Category.objects.annotate(product_count=Count("products"))
        search = self.request.GET.get("search")
        if search:
            qs = qs.filter(Q(name__icontains=search))
        return qs.order_by("-created_at")
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["active_menu"] = "categories"
        context["search_query"] = self.request.GET.get("search", "")
        return context


class CategoryCreateView(StaffRequiredMixin, CreateView):
    model = Category
    form_class = CategoryForm
    template_name = "admin/category_form.html"
    success_url = reverse_lazy("admin_panel:category_list")
    
    def form_valid(self, form):
        messages.success(self.request, "Category created successfully!")
        return super().form_valid(form)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["active_menu"] = "categories"
        context["form_title"] = "Create Category"
        return context


class CategoryUpdateView(StaffRequiredMixin, UpdateView):
    model = Category
    form_class = CategoryForm
    template_name = "admin/category_form.html"
    success_url = reverse_lazy("admin_panel:category_list")
    
    def form_valid(self, form):
        messages.success(self.request, "Category updated successfully!")
        return super().form_valid(form)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["active_menu"] = "categories"
        context["form_title"] = "Edit Category"
        return context


class CategoryDeleteView(StaffRequiredMixin, DeleteView):
    model = Category
    success_url = reverse_lazy("admin_panel:category_list")
    
    def post(self, request, *args, **kwargs):
        """Override post to check for existing products before deleting"""
        self.object = self.get_object()
        
        if self.object.products.exists():
            messages.error(request, "Cannot delete category with existing products.")
            return redirect("admin_panel:category_list")
        
        success_url = self.get_success_url()
        category_name = self.object.name
        
        # Manually handle image deletion via storage backend
        if self.object.image:
            try:
                image_name = self.object.image.name
                storage = self.object.image.storage
                
                # Null the image field before deleting the file
                Category.objects.filter(pk=self.object.pk).update(image=None)
                
                # Delete the file from storage (works with both local and S3)
                try:
                    storage.delete(image_name)
                except Exception:
                    pass  # Ignore if file doesn't exist
                    
            except Exception as e:
                import logging
                logger = logging.getLogger(__name__)
                logger.warning(f"Failed to delete category image: {str(e)}")
        
        # Delete the category object
        try:
            Category.objects.filter(pk=self.object.pk).delete()
            messages.success(request, f"Category '{category_name}' deleted successfully!")
        except Exception as e:
            messages.error(request, f"Error deleting category: {str(e)}")
            
        return redirect(success_url)


# Banner Management Views
class BannerListView(StaffRequiredMixin, ListView):
    model = Banner
    template_name = "admin/banner_list.html"
    context_object_name = "banners"
    paginate_by = 20

    def get_queryset(self):
        qs = Banner.objects.all()
        status = self.request.GET.get("status")
        if status == "active":
            qs = qs.filter(is_active=True)
        elif status == "inactive":
            qs = qs.filter(is_active=False)
        return qs.order_by("display_order", "created_at")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["active_menu"] = "banners"
        context["filter_status"] = self.request.GET.get("status", "")
        context["max_active"] = Banner.MAX_ACTIVE
        return context


class BannerCreateView(StaffRequiredMixin, CreateView):
    model = Banner
    form_class = BannerForm
    template_name = "admin/banner_form.html"
    success_url = reverse_lazy("admin_panel:banner_list")

    def form_valid(self, form):
        messages.success(self.request, "Banner created successfully!")
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["active_menu"] = "banners"
        context["form_title"] = "Create Banner"
        context["max_active"] = Banner.MAX_ACTIVE
        return context


class BannerUpdateView(StaffRequiredMixin, UpdateView):
    model = Banner
    form_class = BannerForm
    template_name = "admin/banner_form.html"
    success_url = reverse_lazy("admin_panel:banner_list")

    def form_valid(self, form):
        messages.success(self.request, "Banner updated successfully!")
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["active_menu"] = "banners"
        context["form_title"] = "Edit Banner"
        context["max_active"] = Banner.MAX_ACTIVE
        return context


class BannerDeleteView(StaffRequiredMixin, DeleteView):
    model = Banner
    success_url = reverse_lazy("admin_panel:banner_list")

    def delete(self, request, *args, **kwargs):
        """Override delete to handle S3 image deletion properly"""
        self.object = self.get_object()
        success_url = self.get_success_url()
        
        # Manually handle S3 file deletion
        if self.object.image:
            try:
                # Store the image name for deletion
                image_name = self.object.image.name
                storage = self.object.image.storage
                
                # Update DB to NULL the image field before deletion
                Banner.objects.filter(pk=self.object.pk).update(image=None)
                
                # Delete the file from S3
                try:
                    storage.delete(image_name)
                except Exception:
                    pass  # Ignore if file doesn't exist
                    
            except Exception as e:
                import logging
                logger = logging.getLogger(__name__)
                logger.warning(f"Failed to delete banner image: {str(e)}")
        
        # Delete the banner object (image field is already None in DB)
        try:
            Banner.objects.filter(pk=self.object.pk).delete()
            messages.success(request, "Banner deleted successfully!")
        except Exception as e:
            messages.error(request, f"Error deleting banner: {str(e)}")
            
        return redirect(success_url)


# Product Management Views
class ProductListView(StaffRequiredMixin, ListView):
    model = Product
    template_name = "admin/product_list.html"
    context_object_name = "products"
    paginate_by = 20
    
    def get_queryset(self):
        qs = Product.objects.select_related("category", "jewellery_detail").prefetch_related(
            "variants", "color_variants__images", "color_variants__size_variants"
        )
        search = self.request.GET.get("search")
        category = self.request.GET.get("category")
        status = self.request.GET.get("status")
        
        if search:
            qs = qs.filter(Q(name__icontains=search) | Q(description__icontains=search))
        if category:
            qs = qs.filter(category_id=category)
        if status == "active":
            qs = qs.filter(is_active=True)
        elif status == "inactive":
            qs = qs.filter(is_active=False)
        
        return qs.order_by("-created_at")
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["active_menu"] = "products"
        context["categories"] = Category.objects.filter(is_active=True)
        context["search_query"] = self.request.GET.get("search", "")
        context["filter_category"] = self.request.GET.get("category", "")
        context["filter_status"] = self.request.GET.get("status", "")
        
        # Calculate inventory for each product
        for product in context["products"]:
            total_inventory = 0
            if product.product_type == "jewellery":
                jd = getattr(product, "jewellery_detail", None)
                total_inventory = (jd.stock_quantity or 0) if jd else 0
            else:
                for color_variant in product.color_variants.all():
                    for size_variant in color_variant.size_variants.all():
                        total_inventory += size_variant.stock_quantity
            product.inventory_count = total_inventory
        
        return context


# ─── Quick Add Color Variant (from product list, clothing only) ───
PRODUCT_TYPE_CLOTHING = "clothing"
ADD_VARIANT_MAX_IMAGES = 3
ADD_VARIANT_ALLOWED_IMAGE_EXTENSIONS = (".jpg", ".jpeg", ".png", ".gif", ".webp")


class AddVariantModalView(StaffRequiredMixin, View):
    """GET: Return modal form HTML for adding a color variant. Product must be clothing."""
    def get(self, request, pk):
        product = get_object_or_404(Product, pk=pk)
        if product.product_type != PRODUCT_TYPE_CLOTHING:
            return JsonResponse(
                {"success": False, "error": "Product is not a clothing product."},
                status=400,
            )
        existing_colors = list(
            product.color_variants.values_list("name", flat=True).order_by("display_order", "name")
        )
        from .admin_forms import STANDARD_SIZES
        return render(
            request,
            "admin/partials/add_variant_modal.html",
            {
                "product": product,
                "existing_colors": existing_colors,
                "standard_sizes": STANDARD_SIZES,
            },
        )


class AddVariantView(StaffRequiredMixin, View):
    """POST: Create ColorVariant + images + sizes. AJAX only, JSON response. Admin-only, CSRF required."""
    def post(self, request, pk):
        product = get_object_or_404(Product, pk=pk)
        if product.product_type != PRODUCT_TYPE_CLOTHING:
            return JsonResponse(
                {"success": False, "errors": {"product": ["Product is not a clothing product."]}},
                status=400,
            )

        errors = {}

        # Color name (required)
        color_name = (request.POST.get("color_name") or "").strip()
        if not color_name:
            errors.setdefault("color_name", []).append("Color name is required.")
        else:
            if product.color_variants.filter(name__iexact=color_name).exists():
                errors.setdefault("color_name", []).append(
                    "A color with this name already exists for this product."
                )

        color_code = (request.POST.get("color_code") or "").strip()[:20]

        # Images: max 3, at least 1 required
        image_keys = [k for k in request.FILES if k.startswith("image_")]
        if len(image_keys) > ADD_VARIANT_MAX_IMAGES:
            errors.setdefault("images", []).append(f"Maximum {ADD_VARIANT_MAX_IMAGES} images allowed.")
        else:
            image_files = []
            for key in sorted(image_keys)[:ADD_VARIANT_MAX_IMAGES]:
                f = request.FILES.get(key)
                if not f:
                    continue
                image_files.append(f)
            if not image_files:
                errors.setdefault("images", []).append("At least one image is required.")
            else:
                for i, f in enumerate(image_files):
                    name = (getattr(f, "name", "") or "").lower()
                    if not any(name.endswith(ext) for ext in ADD_VARIANT_ALLOWED_IMAGE_EXTENSIONS):
                        errors.setdefault("images", []).append(
                            "Invalid file type. Use JPG, PNG, GIF, or WebP."
                        )
                        break
                    try:
                        _validate_image_file(f, required=True)
                    except Exception as e:
                        msgs = getattr(e, "messages", None)
                        msg = (msgs[0] if msgs else str(e)) if msgs or str(e) else "Invalid image."
                        errors.setdefault("images", []).append(msg)
                        break

        # Sizes: at least 1, stock >= 0, no duplicate size
        size_raw = request.POST.get("sizes_json")
        sizes_data = []
        if size_raw:
            try:
                import json as _json
                sizes_data = _json.loads(size_raw)
            except Exception:
                errors.setdefault("sizes", []).append("Invalid sizes data.")
        if not errors.get("sizes") and not sizes_data:
            # Fallback: parse size_0, stock_0, size_1, stock_1, ...
            for i in range(20):
                sz = (request.POST.get(f"size_{i}") or "").strip()
                st = request.POST.get(f"stock_{i}")
                if not sz and (st is None or st == ""):
                    continue
                try:
                    stock_val = int(st) if st not in (None, "") else 0
                except (TypeError, ValueError):
                    stock_val = 0
                if stock_val < 0:
                    errors.setdefault("sizes", []).append("Stock cannot be negative.")
                    break
                sizes_data.append({"size": sz, "stock": stock_val})
        if not errors.get("sizes") and not sizes_data:
            errors.setdefault("sizes", []).append("At least one size is required.")

        if sizes_data and "sizes" not in errors:
            seen_sizes = set()
            for item in sizes_data:
                sz = (item.get("size") or "").strip()
                if not sz:
                    continue
                if sz in seen_sizes:
                    errors.setdefault("sizes", []).append(f"Duplicate size: {sz}.")
                    break
                seen_sizes.add(sz)
                stock_val = item.get("stock")
                if stock_val is None:
                    stock_val = 0
                try:
                    stock_val = int(stock_val)
                except (TypeError, ValueError):
                    stock_val = 0
                if stock_val < 0:
                    errors.setdefault("sizes", []).append("Stock cannot be negative.")
                    break

        if errors:
            return JsonResponse({"success": False, "errors": errors}, status=400)

        # Re-read image files (iterator may be consumed)
        image_files = []
        for key in sorted([k for k in request.FILES if k.startswith("image_")])[:ADD_VARIANT_MAX_IMAGES]:
            f = request.FILES.get(key)
            if f:
                image_files.append(f)

        try:
            with transaction.atomic():
                next_order = (
                    product.color_variants.aggregate(
                        m=Max("display_order")
                    ).get("m") or 0
                ) + 1
                color_variant = ColorVariant.objects.create(
                    product=product,
                    name=color_name,
                    color_code=color_code or "",
                    display_order=next_order,
                    is_active=True,
                )
                for idx, img_file in enumerate(image_files):
                    ColorVariantImage.objects.create(
                        color_variant=color_variant,
                        image=img_file,
                        is_primary=(idx == 0),
                        alt_text="",
                    )
                for item in sizes_data:
                    sz = (item.get("size") or "").strip()
                    if not sz:
                        continue
                    stock_val = item.get("stock")
                    if stock_val is None:
                        stock_val = 0
                    try:
                        stock_val = int(stock_val)
                    except (TypeError, ValueError):
                        stock_val = 0
                    if stock_val < 0:
                        stock_val = 0
                    SizeVariant.objects.create(
                        color_variant=color_variant,
                        size=sz,
                        stock_quantity=stock_val,
                        is_active=True,
                    )
        except Exception as e:
            return JsonResponse(
                {"success": False, "errors": {"__all__": [str(e)]}},
                status=400,
            )

        return JsonResponse({
            "success": True,
            "message": "Variant added successfully.",
            "color_variant_id": color_variant.id,
            "color_name": color_variant.name,
        })


class ProductCreateView(StaffRequiredMixin, TemplateView):
    """GET only. Renders wizard-style create page. Create is done via AJAX (create-basic, then variants/sizes/images)."""
    template_name = "admin/product_form.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["active_menu"] = "products"
        context["form_title"] = "Add Product"
        context["basic_form"] = ProductBasicEditForm(instance=None)
        context["standard_sizes"] = STANDARD_SIZES
        return context


class ProductDeleteView(StaffRequiredMixin, DeleteView):
    model = Product
    success_url = reverse_lazy("admin_panel:product_list")

    def post(self, request, *args, **kwargs):
        """Override post to handle deletion with proper error handling."""
        self.object = self.get_object()
        product_name = self.object.name
        success_url = self.get_success_url()

        # Check if product itself is used in any order
        if OrderItem.objects.filter(product=self.object).exists():
            messages.error(
                request,
                f"Cannot delete product \"{product_name}\". It is linked to existing orders.",
            )
            return redirect(success_url)

        # Check if any ProductVariant (legacy) of this product is used in orders
        if OrderItem.objects.filter(variant__product=self.object).exists():
            messages.error(
                request,
                f"Cannot delete product \"{product_name}\". One or more of its variants are linked to existing orders.",
            )
            return redirect(success_url)

        # Check if any SizeVariant (via ColorVariant) of this product is used in orders
        if OrderItem.objects.filter(size_variant__color_variant__product=self.object).exists():
            messages.error(
                request,
                f"Cannot delete product \"{product_name}\". One or more of its color/size variants are linked to existing orders.",
            )
            return redirect(success_url)

        # Check if any CartItem references this product's variants (additional safety check)
        if CartItem.objects.filter(Q(variant__product=self.object) | Q(size_variant__color_variant__product=self.object)).exists():
            # Remove these cart items before deletion
            CartItem.objects.filter(Q(variant__product=self.object) | Q(size_variant__color_variant__product=self.object)).delete()

        # All checks passed - safe to delete
        # Remove from any active carts first
        CartItem.objects.filter(product=self.object).delete()

        # Delete all images from storage (S3 or local)
        from .models import ColorVariant, ColorVariantImage
        color_variants = ColorVariant.objects.filter(product=self.object)
        for variant in color_variants:
            for img in variant.images.all():
                if img.image:
                    try:
                        image_name = img.image.name
                        storage = img.image.storage
                        ColorVariantImage.objects.filter(pk=img.pk).update(image=None)
                        try:
                            storage.delete(image_name)
                        except Exception:
                            pass
                    except Exception as e:
                        import logging
                        logger = logging.getLogger(__name__)
                        logger.warning(f"Failed to delete color variant image: {str(e)}")

        # Delete the product and all related data
        try:
            self.object.delete()
            messages.success(request, f"Product \"{product_name}\" has been deleted successfully.")
        except ProtectedError as e:
            # This should not happen if our checks are correct, but handle it anyway
            messages.error(
                request,
                f"Cannot delete product \"{product_name}\". It is protected by existing order data.",
            )
        except Exception as e:
            messages.error(request, f"Could not delete product: {str(e)}")

        return redirect(success_url)


class ProductDeleteCheckView(StaffRequiredMixin, View):
    """Check if a product can be deleted and return deletion status"""
    
    def get(self, request, pk):
        product = get_object_or_404(Product, pk=pk)
        
        # Check if product has any orders at all
        all_orders = Order.objects.filter(
            items__product=product
        ).distinct()
        
        # Check if product has any active orders (not delivered or cancelled)
        active_orders = all_orders.exclude(
            status__in=["delivered", "cancelled"]
        ).distinct()
        
        if active_orders.exists():
            # Cannot delete - has active orders
            return JsonResponse({
                'can_delete': False,
                'has_active_orders': True,
                'has_orders': True,
                'message': f'Cannot delete: {active_orders.count()} active order(s)'
            })
        
        if not all_orders.exists():
            # Can completely delete - no orders
            return JsonResponse({
                'can_delete': True,
                'will_delete_completely': True,
                'has_orders': False,
                'message': 'Product will be completely deleted'
            })
        
        # Can deactivate - all orders are delivered/cancelled
        return JsonResponse({
            'can_delete': True,
            'will_delete_completely': False,
            'has_orders': True,
            'message': 'Product will be set to inactive'
        })


# Order Management Views
class OrderListView(StaffRequiredMixin, ListView):
    model = Order
    template_name = "admin/order_list.html"
    context_object_name = "orders"
    paginate_by = 20
    
    def get_queryset(self):
        qs = Order.objects.select_related("address").prefetch_related("items")
        search = self.request.GET.get("search")
        status = self.request.GET.get("status")
        
        if search:
            qs = qs.filter(
                Q(order_number__icontains=search) |
                Q(address__full_name__icontains=search) |
                Q(address__phone__icontains=search)
            )
        if status:
            qs = qs.filter(status=status)
        
        return qs.order_by("-created_at")
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["active_menu"] = "orders"
        context["search_query"] = self.request.GET.get("search", "")
        context["filter_status"] = self.request.GET.get("status", "")
        context["status_choices"] = Order.Status.choices
        return context


class OrderDetailView(StaffRequiredMixin, DetailView):
    model = Order
    template_name = "admin/order_detail.html"
    context_object_name = "order"
    slug_field = "order_number"
    slug_url_kwarg = "order_number"
    
    def get_queryset(self):
        return Order.objects.select_related("address", "payment").prefetch_related(
            "items__product", "items__variant"
        )
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["active_menu"] = "orders"
        context["status_choices"] = Order.Status.choices
        return context


class OrderInvoiceView(StaffRequiredMixin, DetailView):
    """Professional A4 Invoice view for printing"""
    model = Order
    template_name = "admin/order_invoice.html"
    context_object_name = "order"
    slug_field = "order_number"
    slug_url_kwarg = "order_number"
    
    def get_queryset(self):
        return Order.objects.select_related("address", "payment").prefetch_related(
            "items__product", "items__variant"
        )


class OrderUpdateStatusView(StaffRequiredMixin, View):
    def post(self, request, order_number):
        order = get_object_or_404(Order, order_number=order_number)
        new_status = request.POST.get("status")
        
        if new_status in dict(Order.Status.choices):
            order.status = new_status
            order.save(update_fields=["status"])
            messages.success(request, f"Order status updated to {order.get_status_display()}.")
        else:
            messages.error(request, "Invalid status.")
        
        return redirect("admin_panel:order_detail", order_number=order_number)


# Contact Messages Management
class MessageListView(StaffRequiredMixin, ListView):
    model = ContactMessage
    template_name = "admin/message_list.html"
    context_object_name = "contact_messages"
    paginate_by = 20
    
    def get_queryset(self):
        qs = ContactMessage.objects.all()
        status = self.request.GET.get("status")
        
        if status == "unresolved":
            qs = qs.filter(is_resolved=False)
        elif status == "resolved":
            qs = qs.filter(is_resolved=True)
        
        return qs.order_by("-created_at")
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["active_menu"] = "messages"
        context["filter_status"] = self.request.GET.get("status", "")
        return context


class MessageToggleResolvedView(StaffRequiredMixin, View):
    def post(self, request, pk):
        message = get_object_or_404(ContactMessage, pk=pk)
        message.is_resolved = not message.is_resolved
        message.save(update_fields=["is_resolved"])
        
        status_text = "resolved" if message.is_resolved else "unresolved"
        messages.success(request, f"Message marked as {status_text}.")
        
        return redirect("admin_panel:message_list")


class S3FileUploadView(StaffRequiredMixin, View):
    """Handle direct S3 file uploads via AJAX"""
    
    def post(self, request):
        import logging
        logger = logging.getLogger(__name__)
        
        try:
            # Check if file is in request
            if 'file' not in request.FILES:
                return JsonResponse({
                    'success': False,
                    'error': 'No file provided'
                }, status=400)
            
            file = request.FILES['file']
            upload_path = request.POST.get('upload_path', 'uploads')
            
            logger.info(f"Uploading file: {file.name}, size: {file.size}, type: {file.content_type}")
            
            # Validate file size (5MB max)
            max_size = 5 * 1024 * 1024  # 5MB
            if file.size > max_size:
                return JsonResponse({
                    'success': False,
                    'error': f'File size exceeds 5MB limit. Current size: {file.size / (1024*1024):.2f}MB'
                }, status=400)
            
            # Validate image file
            allowed_types = ['image/jpeg', 'image/png', 'image/gif', 'image/webp']
            if file.content_type not in allowed_types:
                return JsonResponse({
                    'success': False,
                    'error': f'Invalid file type. Allowed: JPG, PNG, GIF, WebP'
                }, status=400)
            
            # Save file using Django's storage backend (will use S3 if configured)
            from django.core.files.storage import default_storage
            from django.utils.text import slugify
            from django.conf import settings
            import os
            from datetime import datetime
            
            # Generate unique filename
            ext = os.path.splitext(file.name)[1].lower()
            base_name = slugify(os.path.splitext(file.name)[0])
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"{base_name}_{timestamp}{ext}"
            file_path = f"{upload_path}/{filename}"
            
            logger.info(f"Saving to: {file_path}")
            
            # Upload to S3 with explicit ACL
            if settings.USE_S3:
                # For S3, use the configured storage (no ACL needed, bucket policy handles access)
                from custom_storage import MediaFileStorage
                storage = MediaFileStorage()
                saved_path = storage.save(file_path, file)
                file_url = storage.url(saved_path)
            else:
                saved_path = default_storage.save(file_path, file)
                file_url = default_storage.url(saved_path)
            
            logger.info(f"File saved to: {saved_path}")
            logger.info(f"File URL: {file_url}")
            
            # Verify the file exists
            if settings.USE_S3:
                exists = storage.exists(saved_path)
            else:
                exists = default_storage.exists(saved_path)
                
            if not exists:
                logger.error(f"File not found after upload: {saved_path}")
                return JsonResponse({
                    'success': False,
                    'error': 'Upload failed - file not found after upload'
                }, status=500)
            
            return JsonResponse({
                'success': True,
                'file_path': saved_path,
                'file_url': file_url,
                'file_name': filename,
                'file_size': file.size
            })
            
        except Exception as e:
            logger.error(f"Upload error: {str(e)}", exc_info=True)
            return JsonResponse({
                'success': False,
                'error': f'Upload failed: {str(e)}'
            }, status=500)


class DealOfDayListView(StaffRequiredMixin, TemplateView):
    """Admin view to manage Deal Of The Day products separately from the product form."""
    template_name = "admin/deals_list.html"

    def get_queryset(self):
        qs = Product.objects.select_related("category").order_by(
            "category__name", "name"
        )
        search = (self.request.GET.get("q") or "").strip()
        if search:
            qs = qs.filter(
                Q(name__icontains=search)
                | Q(category__name__icontains=search)
            )
        current_only = self.request.GET.get("current")
        if current_only == "1":
            today = timezone.now().date()
            # Filter for products that are marked as deal and are currently active
            qs = qs.filter(
                Q(
                    is_deal_of_day=True,
                    deal_of_day_start__lte=today,
                    deal_of_day_end__gte=today,
                )
                | Q(
                    is_deal_of_day=True,
                    deal_of_day_start__isnull=True,
                    deal_of_day_end__isnull=True,
                )
            )
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        qs = self.get_queryset()
        paginator = Paginator(qs, 20)
        page = self.request.GET.get("page")
        try:
            page_obj = paginator.page(page)
        except PageNotAnInteger:
            page_obj = paginator.page(1)
        except EmptyPage:
            page_obj = paginator.page(paginator.num_pages)

        context["active_menu"] = "deals"
        context["products"] = page_obj.object_list
        context["page_obj"] = page_obj
        context["paginator"] = paginator
        context["is_paginated"] = paginator.num_pages > 1
        context["search_query"] = (self.request.GET.get("q") or "").strip()
        today = timezone.now().date()
        context["today"] = today
        context["filter_current"] = self.request.GET.get("current") == "1"
        
        # Count current active deals for badge
        if context["filter_current"]:
            context["active_deals_count"] = paginator.count
        else:
            # Count total current deals even when filter is off
            current_deals_qs = Product.objects.filter(
                Q(
                    is_deal_of_day=True,
                    deal_of_day_start__lte=today,
                    deal_of_day_end__gte=today,
                )
                | Q(
                    is_deal_of_day=True,
                    deal_of_day_start__isnull=True,
                    deal_of_day_end__isnull=True,
                )
            )
            context["active_deals_count"] = current_deals_qs.count()
        
        return context

    def post(self, request, *args, **kwargs):
        """Bulk update deal-of-day flags and date ranges for products."""
        products = self.get_queryset()
        updated_count = 0

        for product in products:
            prefix = f"p{product.pk}_"
            is_deal_flag = request.POST.get(f"is_deal_{product.pk}") == "on"
            start_raw = request.POST.get(f"start_{product.pk}") or ""
            end_raw = request.POST.get(f"end_{product.pk}") or ""

            start_date = parse_date(start_raw) if start_raw else None
            end_date = parse_date(end_raw) if end_raw else None

            changed = (
                product.is_deal_of_day != is_deal_flag
                or product.deal_of_day_start != start_date
                or product.deal_of_day_end != end_date
            )
            if not changed:
                continue

            product.is_deal_of_day = is_deal_flag
            product.deal_of_day_start = start_date
            product.deal_of_day_end = end_date
            product.save(update_fields=["is_deal_of_day", "deal_of_day_start", "deal_of_day_end"])
            updated_count += 1

        if updated_count:
            messages.success(request, f"Updated deals for {updated_count} product(s).")
        else:
            messages.info(request, "No changes were made.")

        return redirect("admin_panel:deal_list")


class ReviewListView(StaffRequiredMixin, TemplateView):
    """
    Professional admin moderation panel for Ratings & Reviews.

    Features:
    - Filters: product, rating, date range, approval status.
    - Search: by user (username/email) and product name.
    - Bulk actions: approve, unapprove, delete (soft delete).
    - Pagination.
    """

    template_name = "admin/review_list.html"
    paginate_by = 25

    def get_queryset(self):
        qs = Review.objects.select_related("product", "user", "order").filter(
            is_deleted=False
        )

        request = self.request
        q = (request.GET.get("q") or "").strip()
        product_id = request.GET.get("product")
        rating = request.GET.get("rating")
        status = request.GET.get("status")
        date_from = request.GET.get("date_from")
        date_to = request.GET.get("date_to")

        if q:
            qs = qs.filter(
                Q(product__name__icontains=q)
                | Q(user__username__icontains=q)
                | Q(user__email__icontains=q)
            )
        if product_id:
            try:
                qs = qs.filter(product_id=int(product_id))
            except (TypeError, ValueError):
                pass
        if rating:
            try:
                qs = qs.filter(rating=int(rating))
            except (TypeError, ValueError):
                pass
        if status == "approved":
            qs = qs.filter(is_approved=True)
        elif status == "unapproved":
            qs = qs.filter(is_approved=False)

        if date_from:
            try:
                df = parse_date(date_from)
                if df:
                    qs = qs.filter(created_at__date__gte=df)
            except Exception:
                pass
        if date_to:
            try:
                dt = parse_date(date_to)
                if dt:
                    qs = qs.filter(created_at__date__lte=dt)
            except Exception:
                pass

        return qs.order_by("-created_at")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        qs = self.get_queryset()
        paginator = Paginator(qs, self.paginate_by)
        page_number = self.request.GET.get("page")
        try:
            page_obj = paginator.page(page_number)
        except PageNotAnInteger:
            page_obj = paginator.page(1)
        except EmptyPage:
            page_obj = paginator.page(paginator.num_pages)

        context["active_menu"] = "reviews"
        context["reviews"] = page_obj.object_list
        context["page_obj"] = page_obj
        context["paginator"] = paginator
        context["is_paginated"] = paginator.num_pages > 1

        context["products"] = Product.objects.order_by("name").only("id", "name")
        context["filter_q"] = (self.request.GET.get("q") or "").strip()
        context["filter_product"] = self.request.GET.get("product") or ""
        context["filter_rating"] = self.request.GET.get("rating") or ""
        context["filter_status"] = self.request.GET.get("status") or ""
        context["filter_date_from"] = self.request.GET.get("date_from") or ""
        context["filter_date_to"] = self.request.GET.get("date_to") or ""

        return context

    @transaction.atomic
    def post(self, request, *args, **kwargs):
        """
        Handle bulk moderation actions:
        - approve
        - unapprove
        - delete (soft delete)
        """
        action = request.POST.get("action")
        ids = request.POST.getlist("selected")
        if not action or not ids:
            messages.warning(request, "Please select at least one review and an action.")
            return redirect("admin_panel:review_list")

        try:
            ids_int = [int(x) for x in ids]
        except (TypeError, ValueError):
            messages.error(request, "Invalid review selection.")
            return redirect("admin_panel:review_list")

        reviews = list(
            Review.objects.select_for_update()
            .select_related("product")
            .filter(id__in=ids_int)
        )
        if not reviews:
            messages.info(request, "No reviews found for the selected IDs.")
            return redirect("admin_panel:review_list")

        updated_products = set()

        if action == "approve":
            for r in reviews:
                if not r.is_approved and not r.is_deleted:
                    r.is_approved = True
                    r.save(update_fields=["is_approved"])
                    updated_products.add(r.product_id)
            messages.success(request, "Selected reviews have been approved.")
        elif action == "unapprove":
            for r in reviews:
                if r.is_approved and not r.is_deleted:
                    r.is_approved = False
                    r.save(update_fields=["is_approved"])
                    updated_products.add(r.product_id)
            messages.success(request, "Selected reviews have been unapproved.")
        elif action == "delete":
            for r in reviews:
                if not r.is_deleted:
                    r.is_deleted = True
                    r.save(update_fields=["is_deleted"])
                    updated_products.add(r.product_id)
            messages.success(request, "Selected reviews have been deleted.")
        else:
            messages.error(request, "Unknown action.")
            return redirect("admin_panel:review_list")

        # Product aggregates are kept in sync by Review model signals
        return redirect("admin_panel:review_list")

