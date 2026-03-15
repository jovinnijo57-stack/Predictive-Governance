document.addEventListener('DOMContentLoaded', () => {
    // Add simple entrance animations for cards
    const cards = document.querySelectorAll('.card');
    cards.forEach((card, index) => {
        card.style.opacity = '0';
        card.style.transform = 'translateY(20px)';
        card.style.transition = 'opacity 0.5s ease, transform 0.5s ease';

        setTimeout(() => {
            card.style.opacity = '1';
            card.style.transform = 'translateY(0)';
        }, 100 * (index + 1));
    });

    // Form submission interaction (optional simple client-side validation)
    const form = document.querySelector('form');
    if (form) {
        form.addEventListener('submit', (e) => {
            const btn = form.querySelector('button');
            btn.innerHTML = 'Submitting...';
            btn.style.opacity = '0.7';
        });
    }
});
