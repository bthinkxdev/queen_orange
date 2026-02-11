from django.urls import path

from . import admin_views
from . import admin_report_views

app_name = "admin_panel"

urlpatterns = [
    # Authentication
    path("login/", admin_views.AdminLoginView.as_view(), name="login"),
    path("logout/", admin_views.AdminLogoutView.as_view(), name="logout"),
    
    # Dashboard
    path("", admin_views.AdminDashboardView.as_view(), name="dashboard"),

    # Reports
    path("reports/", admin_report_views.ReportsDashboardView.as_view(), name="report_list"),
    path("reports/orders/", admin_report_views.OrdersReportView.as_view(), name="report_orders"),
    path("reports/sales/", admin_report_views.SalesReportView.as_view(), name="report_sales"),
    path("reports/products/", admin_report_views.ProductPerformanceReportView.as_view(), name="report_products"),
    path("reports/customers/", admin_report_views.CustomerReportView.as_view(), name="report_customers"),
    path("reports/inventory/", admin_report_views.InventoryReportView.as_view(), name="report_inventory"),
    path("reports/api/<str:report_type>/", admin_report_views.ReportApiView.as_view(), name="report_api"),
    path("reports/export/<str:report_type>/<str:format_type>/", admin_report_views.ReportExportView.as_view(), name="report_export"),
    
    # Banners
    path("banners/", admin_views.BannerListView.as_view(), name="banner_list"),
    path("banners/create/", admin_views.BannerCreateView.as_view(), name="banner_create"),
    path("banners/<int:pk>/edit/", admin_views.BannerUpdateView.as_view(), name="banner_edit"),
    path("banners/<int:pk>/delete/", admin_views.BannerDeleteView.as_view(), name="banner_delete"),

    # Categories
    path("categories/", admin_views.CategoryListView.as_view(), name="category_list"),
    path("categories/create/", admin_views.CategoryCreateView.as_view(), name="category_create"),
    path("categories/<int:pk>/edit/", admin_views.CategoryUpdateView.as_view(), name="category_edit"),
    path("categories/<int:pk>/delete/", admin_views.CategoryDeleteView.as_view(), name="category_delete"),
    
    # Deals Of The Day
    path("deals/", admin_views.DealOfDayListView.as_view(), name="deal_list"),
    
    # Products
    path("products/", admin_views.ProductListView.as_view(), name="product_list"),
    path("products/create/", admin_views.ProductCreateView.as_view(), name="product_create"),
    path("products/<int:pk>/edit/", admin_views.ProductUpdateView.as_view(), name="product_edit"),
    path("products/<int:pk>/delete/", admin_views.ProductDeleteView.as_view(), name="product_delete"),
    path("products/<int:pk>/delete-check/", admin_views.ProductDeleteCheckView.as_view(), name="product_delete_check"),
    
    # Orders
    path("orders/", admin_views.OrderListView.as_view(), name="order_list"),
    path("orders/<slug:order_number>/", admin_views.OrderDetailView.as_view(), name="order_detail"),
    path("orders/<slug:order_number>/invoice/", admin_views.OrderInvoiceView.as_view(), name="order_invoice"),
    path("orders/<slug:order_number>/update-status/", admin_views.OrderUpdateStatusView.as_view(), name="order_update_status"),
    
    # Messages
    path("messages/", admin_views.MessageListView.as_view(), name="message_list"),
    path("messages/<int:pk>/toggle-resolved/", admin_views.MessageToggleResolvedView.as_view(), name="message_toggle_resolved"),
    
    # File Upload (S3)
    path("upload/s3/", admin_views.S3FileUploadView.as_view(), name="s3_upload"),
]

