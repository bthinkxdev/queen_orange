// Queen Orange - Product Detail Page

// Parse the size-color-stock mapping
const sizeColorStock = window.sizeColorStock || {};

function updateColorOptions() {
    const selectedSize = document.getElementById('selectedSize').value;
    const colorOptions = document.querySelectorAll('.color-option');
    const colorMessage = document.getElementById('colorMessage');
    const colorOptionsContainer = document.getElementById('colorOptions');
    const sizeColorData = sizeColorStock[selectedSize] || {};
    
    // Check if size has no color variant in stock
    const hasNoColorVariant = sizeColorData['no_color'] === true;
    // Get available colors for this size
    const availableColors = Object.keys(sizeColorData).filter(key => 
        key !== 'no_color' && sizeColorData[key] === true
    );
    
    if (availableColors.length === 0 && !hasNoColorVariant) {
        // Size is completely out of stock
        colorMessage.style.display = 'block';
        colorMessage.textContent = 'Size: N/A';
        colorOptionsContainer.style.display = 'none';
        document.getElementById('selectedColor').value = '';
    } else if (availableColors.length === 0 && hasNoColorVariant) {
        // Size has no color variant
        colorMessage.style.display = 'block';
        colorMessage.textContent = 'Color: N/A';
        colorOptionsContainer.style.display = 'none';
        document.getElementById('selectedColor').value = '';
    } else {
        // Show colors but mark unavailable ones
        colorMessage.style.display = 'none';
        colorOptionsContainer.style.display = 'flex';
        
        colorOptions.forEach((option) => {
            const color = option.dataset.color;
            const isInStock = sizeColorData[color] === true;
            
            if (isInStock) {
                option.style.opacity = '1';
                option.style.cursor = 'pointer';
                option.classList.remove('disabled');
                option.dataset.available = 'true';
            } else {
                option.style.opacity = '0.4';
                option.style.cursor = 'not-allowed';
                option.classList.add('disabled');
                option.dataset.available = 'false';
            }
        });
        
        // Auto-select first available color
        const firstAvailable = Array.from(colorOptions).find(opt => opt.dataset.available === 'true');
        if (firstAvailable) {
            colorOptions.forEach(opt => opt.classList.remove('selected'));
            firstAvailable.classList.add('selected');
            document.getElementById('selectedColor').value = firstAvailable.dataset.color;
        }
    }
}

// Image gallery thumbnail click handler
document.querySelectorAll('.image-thumbnail').forEach((thumb) => {
    thumb.addEventListener('click', () => {
        const mainImage = document.getElementById('mainImage');
        mainImage.src = thumb.dataset.src;
        document.querySelectorAll('.image-thumbnail').forEach((item) => item.classList.remove('active'));
        thumb.classList.add('active');
    });
});

// Size option click handler
document.querySelectorAll('.size-option').forEach((option) => {
    option.addEventListener('click', () => {
        document.querySelectorAll('.size-option').forEach((item) => item.classList.remove('selected'));
        option.classList.add('selected');
        document.getElementById('selectedSize').value = option.dataset.size;
        updateColorOptions();
    });
});

// Color option click handler
document.querySelectorAll('.color-option').forEach((option) => {
    option.addEventListener('click', () => {
        // Only allow selection if color is available
        if (option.dataset.available === 'true') {
            document.querySelectorAll('.color-option').forEach((item) => item.classList.remove('selected'));
            option.classList.add('selected');
            document.getElementById('selectedColor').value = option.dataset.color;
        }
    });
});

// Form submission validation
const cartForm = document.querySelector('form[action*="cart_add"]');
if (cartForm) {
    cartForm.addEventListener('submit', function(e) {
        const selectedSize = document.getElementById('selectedSize').value;
        const selectedColor = document.getElementById('selectedColor').value;
        
        if (!selectedSize) {
            e.preventDefault();
            alert('Please select a size');
            return false;
        }
        
        // Check if selected combination is in stock
        const sizeData = sizeColorStock[selectedSize] || {};
        const colorKey = selectedColor || 'no_color';
        
        if (sizeData[colorKey] !== true) {
            e.preventDefault();
            alert('Selected variant is out of stock');
            return false;
        }
        
        return true;
    });
}

// Initialize color options when page loads
document.addEventListener('DOMContentLoaded', function() {
    updateColorOptions();
});
