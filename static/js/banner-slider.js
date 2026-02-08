/**
 * Banner Slider – horizontal sliding (no fade)
 */
document.addEventListener('DOMContentLoaded', function () {
    const slider = document.getElementById('bannerSlider');
    const slides = slider ? slider.querySelectorAll('.banner-slide') : [];
    
    if (slides.length === 0) return;
    
    const total = slides.length;
    slider.style.width = (total * 100) + '%';
    
    slides.forEach(function (slide) {
        slide.style.flex = '0 0 ' + (100 / total) + '%';
    });
    
    let current = 0;
    
    function goTo(index) {
        current = (index + total) % total;
        const offset = (100 / total) * current;
        slider.style.transform = 'translateX(-' + offset + '%)';
    }
    
    function next() {
        goTo(current + 1);
    }
    
    goTo(0);
    setInterval(next, 3800);
});
