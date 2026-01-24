/**
 * Banner Slider
 * Auto-rotating banner/carousel with smooth fade transitions
 */
document.addEventListener('DOMContentLoaded', function () {
    const slides = document.querySelectorAll('#bannerSlider .banner-slide');
    
    if (slides.length === 0) {
        return; // Exit if no slides found
    }
    
    let current = 0;
    
    function showSlide(idx) {
        slides.forEach((slide, i) => {
            if (i === idx) {
                slide.classList.add('active');
                slide.style.opacity = '1';
            } else {
                slide.classList.remove('active');
                slide.style.opacity = '0';
            }
        });
    }
    
    function nextSlide() {
        current = (current + 1) % slides.length;
        showSlide(current);
    }
    
    // Initialize first slide
    slides[0].classList.add('active');
    
    // Change slide every 3.8 seconds
    setInterval(nextSlide, 3800);
});

