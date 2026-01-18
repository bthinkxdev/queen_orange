# Queen Orange Admin Dashboard

A comprehensive, mobile-responsive admin dashboard for managing your e-commerce store.

## Features

### 📊 Dashboard
- **Real-time Statistics**: View total orders, revenue, products, and unresolved messages
- **Revenue Trends**: 14-day revenue chart using Chart.js
- **Order Status Summary**: Track orders by status
- **Top Selling Products**: See best-performing products (last 30 days)
- **Recent Orders**: Quick access to latest orders
- **Quick Stats**: Weekly and monthly performance metrics

### 📦 Product Management
- Create, edit, and delete products
- Upload multiple product images
- Set primary image for each product
- Manage product variants (size, color, stock)
- Set featured and bestseller flags
- Filter by category and status
- Search functionality

### 🏷️ Category Management
- Create, edit, and delete categories
- Upload category images
- Track product count per category
- Activate/deactivate categories

### 🛍️ Order Management
- View all orders with detailed information
- Filter orders by status
- Search by order number, customer name, or phone
- Update order status (Placed → Confirmed → Shipped → Delivered)
- View customer details and shipping address
- Track payment method and status

### 📧 Contact Messages
- View customer contact messages
- Mark messages as resolved/unresolved
- Filter by resolution status

## Access the Admin Dashboard

### 1. Create a superuser (if not already created)

```bash
python manage.py createsuperuser
```

Follow the prompts to create a username and password.

### 2. Make sure the user is staff

The admin dashboard requires staff permissions. If you're using an existing user:

```python
python manage.py shell
```

```python
from django.contrib.auth import get_user_model
User = get_user_model()
user = User.objects.get(username='your_username')
user.is_staff = True
user.save()
```

### 3. Access the Dashboard

Navigate to: `http://localhost:8000/dashboard/`

Or in production: `https://yourdomain.com/dashboard/`

## Login Credentials

- **URL**: `/dashboard/login/`
- **Username**: Your superuser username
- **Password**: Your superuser password

## URL Structure

```
/dashboard/                              - Dashboard home
/dashboard/login/                        - Admin login
/dashboard/logout/                       - Admin logout
/dashboard/categories/                   - Category list
/dashboard/categories/create/            - Create category
/dashboard/categories/<id>/edit/         - Edit category
/dashboard/categories/<id>/delete/       - Delete category
/dashboard/products/                     - Product list
/dashboard/products/create/              - Create product
/dashboard/products/<id>/edit/           - Edit product
/dashboard/products/<id>/delete/         - Delete product
/dashboard/orders/                       - Order list
/dashboard/orders/<order_number>/        - Order detail
/dashboard/orders/<order_number>/update-status/  - Update order status
/dashboard/messages/                     - Contact messages
/dashboard/messages/<id>/toggle-resolved/  - Toggle message status
```

## Mobile Responsive Design

The admin dashboard is fully responsive and works seamlessly on:
- ✅ Desktop (1920px+)
- ✅ Laptop (1024px - 1920px)
- ✅ Tablet (768px - 1024px)
- ✅ Mobile (320px - 768px)

### Mobile Features
- Collapsible sidebar menu
- Touch-friendly buttons
- Optimized tables
- Responsive forms
- Mobile-friendly navigation

## Security Features

- ✅ Staff-only access (requires `is_staff=True`)
- ✅ Django authentication system
- ✅ CSRF protection on all forms
- ✅ Permission-based redirects
- ✅ Secure logout

## Technologies Used

- **Backend**: Django 6.0+
- **Frontend**: HTML5, CSS3, JavaScript
- **Charts**: Chart.js 4.4.0
- **Icons**: Font Awesome 6.4.0
- **Styling**: Custom CSS with CSS Variables

## Customization

### Colors
Edit `static/css/admin.css` and modify the CSS variables:

```css
:root {
    --primary: #6D4C41;
    --accent: #FF6F61;
    --success: #4CAF50;
    /* ... */
}
```

### Logo
Update the logo in `templates/admin/base.html`:

```html
<h2 class="sidebar-logo">
    <i class="fas fa-crown"></i>
    <span>Your Brand Name</span>
</h2>
```

## Troubleshooting

### Can't login?
- Ensure user has `is_staff=True`
- Check credentials are correct
- Clear browser cache/cookies

### Dashboard not loading?
- Run migrations: `python manage.py migrate`
- Collect static files: `python manage.py collectstatic`
- Check DEBUG=True in development

### Missing statistics?
- Ensure you have orders/products in the database
- Check date ranges in the dashboard view

## Support

For issues or questions:
1. Check this documentation
2. Review Django logs
3. Contact the development team

---

**Created for Queen Orange** 👑🍊

