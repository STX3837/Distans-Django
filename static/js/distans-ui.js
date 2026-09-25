document.addEventListener('DOMContentLoaded', () => {
    // Marca automáticamente la sección activa sin acoplarla a nombres de vistas.
    const currentPath = window.location.pathname.replace(/\/$/, '');
    document.querySelectorAll('.navbar-link').forEach((link) => {
        const linkPath = new URL(link.href, window.location.origin).pathname.replace(/\/$/, '');
        if (linkPath && (currentPath === linkPath || (linkPath !== '' && currentPath.startsWith(`${linkPath}/`)))) {
            link.classList.add('active');
            link.setAttribute('aria-current', 'page');
        }
    });

    // Hace que los mensajes desaparezcan suavemente, sin ocultar errores demasiado pronto.
    document.querySelectorAll('.message-success, .message-info').forEach((message) => {
        window.setTimeout(() => {
            message.style.transition = 'opacity .3s ease, transform .3s ease';
            message.style.opacity = '0';
            message.style.transform = 'translateY(-6px)';
            window.setTimeout(() => message.remove(), 320);
        }, 6000);
    });
});
