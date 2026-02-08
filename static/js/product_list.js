// Get CSRF token from cookie (Django sets this automatically)
function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        const cookies = document.cookie.split(';');
        for (let i = 0; i < cookies.length; i++) {
            const cookie = cookies[i].trim();
            if (cookie.substring(0, name.length + 1) === (name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}

// Handle product delete button with conditional logic
document.addEventListener('DOMContentLoaded', function() {
    const deleteButtons = document.querySelectorAll('.delete-btn');
    const csrftoken = getCookie('csrftoken');
    
    deleteButtons.forEach(btn => {
        btn.addEventListener('click', function(e) {
            e.preventDefault();
            const productId = this.getAttribute('data-product-id');
            const productName = this.getAttribute('data-product-name');
            
            // Get the base URL from data attribute or construct it
            const deleteCheckUrl = `/dashboard/products/${productId}/delete-check/`;
            const deleteUrl = `/dashboard/products/${productId}/delete/`;
            
            // Check if product can be deleted
            fetch(deleteCheckUrl)
                .then(response => response.json())
                .then(data => {
                    if (data.can_delete) {
                        let message;
                        if (data.will_delete_completely) {
                            message = `Are you sure you want to DELETE "${productName}" completely?\n\nThis product has no orders and will be permanently removed.`;
                        } else {
                            message = `Are you sure you want to set "${productName}" to INACTIVE?\n\n`;
                        }
                        
                        if (confirm(message)) {
                            // Submit the delete form with CSRF token
                            const form = document.createElement('form');
                            form.method = 'post';
                            form.action = deleteUrl;
                            
                            // Create CSRF token input
                            const csrfInput = document.createElement('input');
                            csrfInput.type = 'hidden';
                            csrfInput.name = 'csrfmiddlewaretoken';
                            csrfInput.value = csrftoken;
                            
                            form.appendChild(csrfInput);
                            document.body.appendChild(form);
                            form.submit();
                        }
                    } else {
                        // Cannot delete - show error
                        alert(`❌ Cannot Delete\n\n"${productName}" has ${data.active_orders ? 'active orders' : 'pending orders'}.\n\n${data.message}\n\nThe product can only be deleted once all orders are delivered or cancelled.`);
                    }
                })
                .catch(function() {
                    alert('An error occurred while checking deletion status.');
                });
        });
    });
});
