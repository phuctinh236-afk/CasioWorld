document.addEventListener('DOMContentLoaded', function() {
    // Xử lý thanh điều hướng dưới cùng (Bottom Nav)
    const navItems = document.querySelectorAll('.nav-item');
    navItems.forEach(item => {
        item.addEventListener('click', function() {
            navItems.forEach(nav => nav.classList.remove('active'));
            this.classList.add('active');
        });
    });

    // Xử lý thanh thể loại (Categories: HOT, ĐÁ GÀ, Slots...)
    const catItems = document.querySelectorAll('.cat-item');
    catItems.forEach(item => {
        item.addEventListener('click', function() {
            catItems.forEach(cat => cat.classList.remove('active'));
            this.classList.add('active');
        });
    });
});
