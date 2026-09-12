from fastapi import APIRouter
from fastapi.responses import HTMLResponse, RedirectResponse

from app.web.layout import render_page

router = APIRouter()


def render_auth_page() -> HTMLResponse:
    return render_page(
        "Authentification | Smart Fridge",
        "/login",
        """
        <section class="auth-shell">
            <div class="auth-card auth-card--green">
                <div class="auth-badge">Smart Fridge</div>
                <h1>Connexion</h1>
                <p>Accédez à votre frigo intelligent et à vos recommandations.</p>

                <form id="login-form" class="auth-form">
                    <div class="field field--password">
                        <label for="login-email">Email</label>
                        <input id="login-email" name="email" type="email" placeholder="vous@example.com" required />
                    </div>
                    <div class="field field--password">
                        <label for="login-password">Mot de passe</label>
                        <div class="password-input-wrap">
                            <input id="login-password" name="password" type="password" placeholder="••••••••" required />
                            <button type="button" class="password-toggle" data-target="login-password">Voir</button>
                        </div>
                    </div>
                    <button type="submit" class="btn btn-primary">Se connecter</button>
                    <div id="login-message" class="message message--hidden"></div>
                </form>
            </div>

            <div class="auth-card auth-card--dark">
                <div class="auth-badge auth-badge--light">Nouveau</div>
                <h2>Créer un compte</h2>
                <p>Commencez à organiser votre alimentation et vos achats plus intelligemment.</p>

                <form id="register-form" class="auth-form">
                    <div class="field field--password">
                        <label for="register-email">Email</label>
                        <input id="register-email" name="email" type="email" placeholder="nouveau@example.com" required />
                    </div>
                    <div class="field field--password">
                        <label for="register-password">Mot de passe</label>
                        <div class="password-input-wrap">
                            <input id="register-password" name="password" type="password" placeholder="Minimum 6 caractères" required />
                            <button type="button" class="password-toggle" data-target="register-password">Voir</button>
                        </div>
                    </div>
                    <button type="submit" class="btn btn-secondary">S'inscrire</button>
                    <div id="register-message" class="message message--hidden"></div>
                </form>
            </div>
        </section>

        <script>
            function attachPasswordToggle(button) {
                const target = document.getElementById(button.dataset.target);
                if (!target) return;
                button.addEventListener('click', () => {
                    const show = target.type === 'password';
                    target.type = show ? 'text' : 'password';
                    button.textContent = show ? 'Masquer' : 'Voir';
                });
            }

            document.querySelectorAll('.password-toggle').forEach(attachPasswordToggle);
            localStorage.removeItem('smartfridge_token');

            function formatErrorMessage(detail) {
                if (!detail) return 'Une erreur est survenue.';

                if (typeof detail === 'string') return detail;

                if (Array.isArray(detail)) {
                    const firstError = detail[0];
                    if (firstError && typeof firstError === 'object') {
                        if (firstError.msg) return firstError.msg;
                        if (firstError.message) return firstError.message;
                    }
                    return detail.map(item => typeof item === 'string' ? item : (item?.msg || 'Erreur')).join(' ');
                }

                if (typeof detail === 'object') {
                    if (detail.msg) return detail.msg;
                    if (detail.message) return detail.message;
                }

                return 'Une erreur est survenue.';
            }

            async function submitAuthForm(formId, endpoint, messageId, successText) {
                const form = document.getElementById(formId);
                const messageBox = document.getElementById(messageId);
                const submitButton = form.querySelector('button[type="submit"]');

                form.addEventListener('submit', async (event) => {
                    event.preventDefault();
                    const formData = new FormData(form);
                    const payload = Object.fromEntries(formData.entries());

                    if (payload.password && payload.password.length < 6) {
                        messageBox.textContent = 'Le mot de passe doit contenir au moins 6 caractères.';
                        messageBox.className = 'message message--error';
                        return;
                    }

                    submitButton.disabled = true;
                    submitButton.textContent = 'Chargement...';
                    messageBox.className = 'message message--hidden';

                    try {
                        const response = await fetch(endpoint, {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify(payload),
                            credentials: 'include'
                        });

                        const result = await response.json().catch(() => ({}));
                        if (!response.ok) {
                            throw new Error(formatErrorMessage(result.detail));
                        }

                        if (formId === 'login-form' && result.access_token) {
                            localStorage.setItem('smartfridge_token', result.access_token);
                        }

                        messageBox.textContent = successText;
                        messageBox.className = 'message message--success';
                        form.reset();

                        if (formId === 'login-form') {
                            window.location.href = '/';
                        } else {
                            window.location.href = '/login';
                        }
                    } catch (error) {
                        messageBox.textContent = error.message;
                        messageBox.className = 'message message--error';
                    } finally {
                        submitButton.disabled = false;
                        submitButton.textContent = formId === 'login-form' ? 'Se connecter' : "S'inscrire";
                    }
                });
            }

            submitAuthForm('login-form', '/auth/login', 'login-message', 'Connexion réussie. Redirection...');
            submitAuthForm('register-form', '/auth/register', 'register-message', 'Compte créé avec succès. Redirection...');
        </script>
        """
    )


@router.get("/login", response_class=HTMLResponse)
def login_page():
    return render_auth_page()


@router.post("/logout")
def logout():
    response = RedirectResponse(url="/login", status_code=302)
    response.delete_cookie(key="access_token")
    return response
