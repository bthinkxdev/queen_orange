/**
 * Banner Slider – horizontal sliding, wrapper height adapts to active slide image
 */
document.addEventListener('DOMContentLoaded', function () {
    const wrapper = document.querySelector('.banner-slider-wrapper');
    const slider = document.getElementById('bannerSlider');
    const slides = slider ? slider.querySelectorAll('.banner-slide') : [];
    
    if (slides.length === 0 || !wrapper) return;
    
    const total = slides.length;
    slider.style.width = (total * 100) + '%';
    
    slides.forEach(function (slide) {
        slide.style.flex = '0 0 ' + (100 / total) + '%';
    });
    
    let current = 0;
    
    function setWrapperHeight() {
        const img = slides[current];
        if (!img || !img.naturalWidth) return;
        const w = wrapper.offsetWidth;
        const h = (img.naturalHeight / img.naturalWidth) * w;
        wrapper.style.height = h + 'px';
    }
    
    function goTo(index) {
        current = (index + total) % total;
        const offset = (100 / total) * current;
        slider.style.transform = 'translateX(-' + offset + '%)';
        setWrapperHeight();
    }
    
    function next() {
        goTo(current + 1);
    }
    
    goTo(0);
    slides.forEach(function (img) {
        if (img.complete) setWrapperHeight();
        else img.addEventListener('load', setWrapperHeight);
    });
    window.addEventListener('resize', setWrapperHeight);
    
    setInterval(next, 5000);
});
