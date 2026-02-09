from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.mixins import UserPassesTestMixin
from django.contrib.auth.decorators import user_passes_test
from django.db.models import Count, Sum, Q, F
from django.db.models.functions import TruncDate
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.utils import timezone
from django.views.generic import (
    CreateView,
    DeleteView,
    DetailView,
    ListView,
    TemplateView,
    UpdateView,
    View,
)
from datetime import timedelta

from .models import (
    Banner,
    Category,
    ContactMessage,
    Order,
    OrderItem,
    Product,
    ProductVariant,
    SizeVariant,
)
from .admin_forms import (
    AdminLoginForm,
    BannerForm,
    CategoryForm,
    ColorVariantFormSet,
    ColorVariantImageFormSet,
    ProductForm,
    ProductVariantFormSet,
    SizeVariantFormSet,
)


class StaffRequiredMixin(UserPassesTestMixin):
    """Mixin to require staff/admin access"""
    
    def test_func(self):
        return self.request.user.is_authenticated and self.request.user.is_staff
    
    def handle_no_permission(self):
        if not self.request.user.is_authenticated:
            return redirect("admin_panel:login")
        messages.error(self.request, "You don't have permission to access this area.")
        return redirect("store:home")


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
        
        # Top selling products (last 30 days)
        top_products = (
            Product.objects.filter(
                order_items__order__created_at__gte=last_30_days
            )
            .annotate(
                total_sold=Sum("order_items__quantity"),
                revenue=Sum(F("order_items__quantity") * F("order_items__unit_price"))
            )
            .order_by("-total_sold")[:5]
        )
        
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
        category = self.get_object()
        if category.products.exists():
            messages.error(request, "Cannot delete category with existing products.")
            return redirect("admin_panel:category_list")
        
        messages.success(request, f"Category '{category.name}' deleted successfully!")
        return super().post(request, *args, **kwargs)


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

    def post(self, request, *args, **kwargs):
        banner = self.get_object()
        messages.success(request, "Banner deleted successfully!")
        return super().post(request, *args, **kwargs)


# Product Management Views
class ProductListView(StaffRequiredMixin, ListView):
    model = Product
    template_name = "admin/product_list.html"
    context_object_name = "products"
    paginate_by = 20
    
    def get_queryset(self):
        qs = Product.objects.select_related("category").prefetch_related(
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
            for color_variant in product.color_variants.all():
                for size_variant in color_variant.size_variants.all():
                    total_inventory += size_variant.stock_quantity
            product.inventory_count = total_inventory
        
        return context


class ProductCreateView(StaffRequiredMixin, CreateView):
    model = Product
    form_class = ProductForm
    template_name = "admin/product_form.html"
    success_url = reverse_lazy("admin_panel:product_list")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if self.request.POST:
            context["color_formset"] = ColorVariantFormSet(
                self.request.POST, self.request.FILES, prefix="colors"
            )
        else:
            context["color_formset"] = ColorVariantFormSet(prefix="colors")
        color_formset = context["color_formset"]
        context["color_formsets_data"] = []
        for i, cf in enumerate(color_formset.forms):
            prefix_img = "color-%s-images" % i
            prefix_sz = "color-%s-sizes" % i
            if self.request.POST:
                context["color_formsets_data"].append({
                    "color_form": cf,
                    "image_formset": ColorVariantImageFormSet(
                        self.request.POST, self.request.FILES, prefix=prefix_img
                    ),
                    "size_formset": SizeVariantFormSet(self.request.POST, prefix=prefix_sz),
                })
            else:
                cv = getattr(cf, "instance", None)
                inst = cv if (cv and cv.pk) else None
                context["color_formsets_data"].append({
                    "color_form": cf,
                    "image_formset": ColorVariantImageFormSet(instance=inst, prefix=prefix_img),
                    "size_formset": SizeVariantFormSet(instance=inst, prefix=prefix_sz),
                })
        context["active_menu"] = "products"
        context["form_title"] = "Create Product"
        return context

    def form_valid(self, form):
        self.object = form.save()
        color_formset = ColorVariantFormSet(
            self.request.POST, self.request.FILES, instance=self.object, prefix="colors"
        )
        if not color_formset.is_valid():
            return self.form_invalid(form)
        color_formset.save()
        for i, cf in enumerate(color_formset.forms):
            if cf.cleaned_data and cf.cleaned_data.get("DELETE"):
                continue
            cv = cf.instance
            if not cv.pk:
                continue
            prefix_img = "color-%s-images" % i
            prefix_sz = "color-%s-sizes" % i
            image_fs = ColorVariantImageFormSet(
                self.request.POST, self.request.FILES, instance=cv, prefix=prefix_img
            )
            size_fs = SizeVariantFormSet(self.request.POST, instance=cv, prefix=prefix_sz)
            if image_fs.is_valid():
                image_fs.save()
            if size_fs.is_valid():
                size_fs.save()
        messages.success(self.request, "Product created successfully!")
        return redirect(self.success_url)


class ProductUpdateView(StaffRequiredMixin, UpdateView):
    model = Product
    form_class = ProductForm
    template_name = "admin/product_form.html"
    success_url = reverse_lazy("admin_panel:product_list")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        product = self.object
        if self.request.POST:
            context["color_formset"] = ColorVariantFormSet(
                self.request.POST, self.request.FILES, instance=product, prefix="colors"
            )
        else:
            context["color_formset"] = ColorVariantFormSet(
                instance=product, prefix="colors"
            )
        color_formset = context["color_formset"]
        context["color_formsets_data"] = []
        for i, cf in enumerate(color_formset.forms):
            prefix_img = "color-%s-images" % i
            prefix_sz = "color-%s-sizes" % i
            cv = getattr(cf, "instance", None)
            inst = cv if (cv and cv.pk) else None
            if self.request.POST:
                context["color_formsets_data"].append({
                    "color_form": cf,
                    "image_formset": ColorVariantImageFormSet(
                        self.request.POST, self.request.FILES, instance=inst, prefix=prefix_img
                    ),
                    "size_formset": SizeVariantFormSet(
                        self.request.POST, instance=inst, prefix=prefix_sz
                    ),
                })
            else:
                context["color_formsets_data"].append({
                    "color_form": cf,
                    "image_formset": ColorVariantImageFormSet(instance=inst, prefix=prefix_img),
                    "size_formset": SizeVariantFormSet(instance=inst, prefix=prefix_sz),
                })
        context["active_menu"] = "products"
        context["form_title"] = "Edit Product"
        return context

    def form_valid(self, form):
        self.object = form.save()
        color_formset = ColorVariantFormSet(
            self.request.POST, self.request.FILES, instance=self.object, prefix="colors"
        )
        if not color_formset.is_valid():
            return self.form_invalid(form)
        color_formset.save()
        for i, cf in enumerate(color_formset.forms):
            if cf.cleaned_data and cf.cleaned_data.get("DELETE"):
                continue
            cv = cf.instance
            if not cv.pk:
                continue
            prefix_img = "color-%s-images" % i
            prefix_sz = "color-%s-sizes" % i
            image_fs = ColorVariantImageFormSet(
                self.request.POST, self.request.FILES, instance=cv, prefix=prefix_img
            )
            size_fs = SizeVariantFormSet(self.request.POST, instance=cv, prefix=prefix_sz)
            if image_fs.is_valid():
                image_fs.save()
            if size_fs.is_valid():
                size_fs.save()
        messages.success(self.request, "Product updated successfully!")
        return redirect(self.success_url)


class ProductDeleteView(StaffRequiredMixin, DeleteView):
    model = Product
    success_url = reverse_lazy("admin_panel:product_list")
    
    def post(self, request, *args, **kwargs):
        product = self.get_object()
        
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
            order_count = active_orders.count()
            order_numbers = ", ".join([order.order_number for order in active_orders[:5]])
            if order_count > 5:
                order_numbers += f", and {order_count - 5} more"
            
            messages.error(
                request,
                f"Cannot delete product '{product.name}' because it has {order_count} active order(s) "
                f"({order_numbers}). This product can only be inactive once all associated orders are "
                f"delivered or cancelled."
            )
            return redirect("admin_panel:product_list")
        
        # If there are no orders at all, completely delete
        if not all_orders.exists():
            messages.success(request, f"Product '{product.name}' deleted successfully!")
            return super().post(request, *args, **kwargs)
        
        # If all orders are delivered/cancelled, set to inactive instead of deleting
        if all_orders.exists():
            product.is_active = False
            product.save()
            messages.success(
                request,
                f"Product '{product.name}' has been set to inactive."
            )
            return redirect("admin_panel:product_list")


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
    context_object_name = "messages"
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

