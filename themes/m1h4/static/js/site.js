(() => {
    const appearance = document.getElementById('appearance');
    const sources = document.querySelectorAll('[data-theme-source]');
    const updatePictures = () => {
        const theme = document.documentElement.dataset.theme;
        for (const source of sources) {
            source.media = theme === 'dark' ? 'all' : theme === 'light' ? 'not all' : '(prefers-color-scheme: dark)';
        }
    };
    updatePictures();
    if (!appearance) return;
    appearance.value = document.documentElement.dataset.theme || 'system';
    appearance.closest('label').hidden = false;
    appearance.addEventListener('change', () => {
        if (appearance.value === 'system') delete document.documentElement.dataset.theme;
        else document.documentElement.dataset.theme = appearance.value;
        updatePictures();
        try {
            if (appearance.value === 'system') localStorage.removeItem('appearance');
            else localStorage.setItem('appearance', appearance.value);
        } catch (_) { /* The selection still applies for this visit. */ }
    });
})();

for (const gallery of document.querySelectorAll('.gallery')) {
    const pager = gallery.querySelector('.gallery-pager');
    if (!pager) continue;
    const buttons = [...pager.querySelectorAll('button')];
    const track = gallery.querySelector('.gallery-track');
    const slides = [...track.children];
    let current;

    function syncPage() {
        if (!track.clientWidth) return;
        const paged = track.scrollWidth > track.clientWidth + 1;
        const index = paged ? Math.max(0, Math.min(slides.length - 1, Math.round(track.scrollLeft / track.clientWidth))) : -1;
        if (index === current) return;
        current = index;
        for (const [i, button] of buttons.entries()) {
            if (i === index) button.setAttribute('aria-current', 'true');
            else button.removeAttribute('aria-current');
            slides[i].inert = paged && i !== index;
        }
    }

    for (const [index, button] of buttons.entries()) {
        button.addEventListener('click', () => track.scrollTo({ left: index * track.clientWidth }));
    }
    pager.addEventListener('keydown', event => {
        const index = buttons.indexOf(event.target);
        if (event.key !== 'ArrowLeft' && event.key !== 'ArrowRight') return;
        event.preventDefault();
        const next = buttons[Math.max(0, Math.min(buttons.length - 1, index + (event.key === 'ArrowRight' ? 1 : -1)))];
        next.focus();
        next.click();
    });
    track.addEventListener('scroll', syncPage, { passive: true });
    track.addEventListener('scrollend', () => {
        if (current < 0) return;
        // Some mobile browsers can finish a swipe between snap points.
        const left = current * track.clientWidth;
        if (Math.abs(track.scrollLeft - left) > 1) track.scrollTo({ left });
    });
    new ResizeObserver(syncPage).observe(track);
    syncPage();
    track.removeAttribute('tabindex');
    pager.hidden = false;
}
