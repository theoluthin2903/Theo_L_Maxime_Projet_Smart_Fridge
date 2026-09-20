from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from jose import JWTError, jwt

from app.core.jwt import ALGORITHM, SECRET_KEY
from app.db.database import SessionLocal
from app.db.models import UserDB


def get_token_from_request(request: Request) -> str | None:
    token = request.cookies.get("access_token")
    if token:
        return token

    auth_header = request.headers.get("authorization")
    if auth_header and auth_header.lower().startswith("bearer "):
        return auth_header.split(" ", 1)[1]

    return None


def require_auth(request: Request) -> RedirectResponse | None:
    if request.method.upper() in {"GET", "HEAD", "OPTIONS"}:
        return None

    token = get_token_from_request(request)
    if not token:
        return RedirectResponse(url="/login", status_code=302)

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        if not payload.get("sub"):
            return RedirectResponse(url="/login", status_code=302)
    except JWTError:
        return RedirectResponse(url="/login", status_code=302)

    return None


def register_auth_middleware(app: FastAPI) -> None:
    @app.middleware("http")
    async def auth_middleware(request: Request, call_next):
        public_paths = {"/login", "/auth/login", "/auth/register", "/docs", "/openapi.json"}
        path = request.url.path

        if path.startswith("/static") or path in public_paths:
            return await call_next(request)

        if path.startswith("/auth/"):
            return await call_next(request)

        redirect = require_auth(request)
        if redirect:
            return redirect

        return await call_next(request)


def nav(active: str, is_admin: bool = False) -> str:
    links = [
        ("/", "Accueil"),
        ("/fridge", "Frigo"),
        ("/products", "Produits"),
        ("/recipes", "Recettes"),
        ("/nutrition", "Nutrition"),
        ("/alerts", "Alertes"),
        ("/profile", "Profile"),
    ]
    if is_admin:
        links.append(("/admin", "Administration"))
    html = []
    for path, label in links:
        is_active = path == active
        classes = (
            'block rounded-xl bg-white/20 px-4 py-3 font-semibold text-white'
            if is_active
            else 'block rounded-xl bg-white/10 px-4 py-3 text-white/90 transition hover:bg-white/15'
        )
        html.append(f'<a href="{path}" class="{classes}">{label}</a>')
    return "".join(html)


def get_user_email_from_request(request: Request) -> str | None:
    token = get_token_from_request(request)
    if not token:
        return None

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("sub")
        if not user_id:
            return None
        user_id = int(user_id)

        with SessionLocal() as db:
            user = db.query(UserDB).filter(UserDB.id == user_id).first()
            if user:
                return user.email
    except (JWTError, ValueError, TypeError):
        return None

    return None


def is_admin_from_request(request: Request) -> bool:
    token = get_token_from_request(request)
    if not token:
        return False
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("sub")
        if not user_id:
            return False
        with SessionLocal() as db:
            user = db.query(UserDB).filter(UserDB.id == int(user_id)).first()
            return bool(user and user.is_admin)
    except (JWTError, ValueError, TypeError):
        return False


def render_page(title: str, active: str, body: str, request: Request | None = None) -> HTMLResponse:
    if request is not None:
        user_email = get_user_email_from_request(request)
        is_logged_in = bool(user_email)
        is_admin = is_admin_from_request(request)
        welcome_block = f"""
            <div class="mt-6 rounded-xl border border-white/15 bg-white/5 p-3 text-sm text-white/90">
                <div class="text-xs uppercase tracking-[0.14em] text-white/60">Bienvenue</div>
                <div class="mt-1 truncate font-semibold text-white">{user_email or 'Utilisateur'}</div>
            </div>
        """ if is_logged_in else ""
    else:
        is_logged_in = False
        is_admin = False
        welcome_block = ""

    logout_button = """
        <form method="post" action="/logout" class="mt-4">
            <button type="submit" class="w-full rounded-xl bg-white/10 px-4 py-3 text-left font-semibold text-white transition hover:bg-white/15">
                Se déconnecter
            </button>
        </form>
    """ if is_logged_in else ""

    login_button = """
    <a href="/login" class="mt-4 block w-full rounded-xl bg-white px-4 py-3 text-center font-bold text-green-800 shadow-sm transition hover:bg-green-50 dark:bg-green-600 dark:text-white dark:hover:bg-green-700">
        Se connecter
    </a>
""" if not is_logged_in else ""
    theme_toggle_button = """
        <button
            type="button"
            id="theme-toggle"
            onclick="toggleTheme()"
            class="mt-4 flex w-full items-center justify-between rounded-xl bg-white/10 px-4 py-3 font-semibold text-white transition hover:bg-white/15"
        >
            <span>Mode sombre</span>
            <span id="theme-toggle-icon" aria-hidden="true">🌙</span>
        </button>
    """

    visitor_class = "" if is_logged_in else "visitor-mode"

    return HTMLResponse(
        f"""
        <!DOCTYPE html>
        <html lang="fr">
        <head>
            <meta charset="UTF-8" />
            <meta name="viewport" content="width=device-width, initial-scale=1.0" />
            <title>{title}</title>
            <script>
                (function () {{
                    var stored = localStorage.getItem('theme');
                    var prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
                    var theme = stored || (prefersDark ? 'dark' : 'light');
                    if (theme === 'dark') {{
                        document.documentElement.classList.add('dark');
                    }}
                }})();
            </script>
            <script src="https://cdn.tailwindcss.com"></script>
            <script>
                tailwind.config = {{
                    darkMode: 'class',
                    theme: {{
                        extend: {{
                            colors: {{
                                brand: {{
                                    50: '#f0fdf4',
                                    100: '#dcfce7',
                                    600: '#16a34a',
                                    700: '#15803d',
                                    800: '#166534'
                                }}
                            }}
                        }}
                    }}
                }}
            </script>
            <link rel="stylesheet" href="/static/styles.css?v=4" />
            <style>
                /* Visiteur : les formulaires de modification sont visibles mais inutilisables. */
                .visitor-mode form[method="post"] input,
                .visitor-mode form[method="post"] textarea,
                .visitor-mode form[method="post"] select,
                .visitor-mode form[method="post"] button,
                .visitor-mode form[method="POST"] input,
                .visitor-mode form[method="POST"] textarea,
                .visitor-mode form[method="POST"] select,
                .visitor-mode form[method="POST"] button {{
                    pointer-events: none;
                    opacity: 0.55;
                    cursor: not-allowed;
                }}
            </style>
        </head>
        <body class="bg-green-50 text-slate-800 antialiased transition-colors duration-200 dark:bg-slate-900 dark:text-slate-100 {visitor_class}">
            <div class="flex min-h-screen flex-col md:flex-row">
                <aside class="w-full bg-gradient-to-b from-green-800 to-green-600 p-6 text-white transition-colors duration-200 dark:from-slate-800 dark:to-slate-950 md:w-64">
                    <div class="mb-8 text-2xl font-black">Smart Fridge</div>
                    <nav class="flex flex-col gap-3">
                        {nav(active, is_admin)}
                    </nav>
                    {theme_toggle_button}
                    {welcome_block}
                    {login_button}
                    {logout_button}
                </aside>
                <main class="flex-1 p-6 md:p-8">
                    <div class="space-y-6">
                        {body}
                    </div>
                </main>
            </div>
            <script>
                function toggleTheme() {{
                    var isDark = document.documentElement.classList.toggle('dark');
                    localStorage.setItem('theme', isDark ? 'dark' : 'light');
                    updateThemeIcon();
                }}
                function updateThemeIcon() {{
                    var icon = document.getElementById('theme-toggle-icon');
                    if (icon) {{
                        icon.textContent = document.documentElement.classList.contains('dark') ? '🌙' : '☀️';
                    }}
                }}
                document.addEventListener('DOMContentLoaded', updateThemeIcon);
            </script>
        </body>
        </html>
        """
    )