# Smart Fridge — durcissement de la sécurité

## À faire après avoir copié les fichiers
1. **Clé JWT** : `JWT_SECRET_KEY` doit faire au moins 32 caractères, sinon l'application refuse de démarrer. Pour en générer une :
   `python -c "import secrets; print(secrets.token_urlsafe(48))"`
   Mettez-la dans `.env` en local, et dans les variables d'environnement sur Scalingo.
2. **Sur Scalingo** : ajoutez `TRUST_PROXY=1`, pour que la limite de tentatives de connexion utilise la vraie adresse des visiteurs.
3. **Tests** : `pip install -r requirements-dev.txt`, puis `python -m pytest` (11 tests).

Le fichier `.env.example` liste toutes les variables utilisées.

## Ce qui a été corrigé

### XSS stockée (alertes, frigo)
Le nom d'un produit et le nom d'une recette (envoyé par un champ caché du formulaire, donc modifiable) étaient affichés **sans échappement** sur la page Alertes. Un nom comme `<script>…</script>` aurait exécuté du code dans la page.
- Les titres, messages, icônes et badges des alertes sont maintenant échappés (`html.escape`).
- Même chose pour la liste du frigo affichée en cas d'erreur, et pour l'adresse e-mail dans la barre latérale.
- L'inscription refuse les adresses qui ne sont pas des e-mails valides (plus de HTML possible dans une adresse).

### Jeton de connexion exposé au JavaScript
Le jeton était posé dans un cookie `HttpOnly`, inaccessible au JavaScript. Mais il était aussi copié dans le `localStorage`, sans jamais y être relu. Un script injecté aurait donc pu le voler. Il reste maintenant uniquement dans le cookie. Les anciennes copies sont effacées à la prochaine visite de la page de connexion.

### Force brute sur la connexion
Il n'y avait aucune limite au nombre d'essais.
- **5 échecs en 15 minutes** bloquent la connexion (réponse 429 avec `Retry-After`). Le blocage compte par adresse IP et par compte : changer d'adresse IP ne suffit pas.
- L'en-tête `X-Forwarded-For` n'est lu que si `TRUST_PROXY=1` : un attaquant ne peut pas le falsifier pour contourner la limite.
- **Temps de réponse identique** que le compte existe ou non (un hash est toujours vérifié), pour ne pas révéler quelles adresses ont un compte.

### Cookie et en-têtes
- Le cookie de connexion est marqué `Secure` dès que le site est servi en HTTPS, y compris derrière le proxy de Scalingo. Avant, il ne l'était jamais.
- Nouveaux en-têtes sur toutes les pages : `X-Content-Type-Options`, `X-Frame-Options: DENY` (anti-clickjacking), `Referrer-Policy`, `Permissions-Policy`, et `Strict-Transport-Security` en HTTPS.

### Clé JWT
Sans `JWT_SECRET_KEY`, l'application démarrait mais plantait à la première connexion. Avec une clé courte, les jetons étaient plus faciles à falsifier. Elle refuse maintenant de démarrer, avec un message qui explique comment générer une clé. Les dates des jetons utilisent l'heure UTC explicite (`datetime.utcnow` est déprécié).

### Règles de mot de passe
À l'inscription : **8 caractères minimum** (au lieu de 6), au moins une lettre et un chiffre, et 128 caractères maximum. Les comptes existants peuvent toujours se connecter avec leur ancien mot de passe.

## Tests
`tests/test_security.py` contient 11 tests. Sur la version précédente, **10 échouent**. Ils couvrent la XSS dans les alertes, le blocage après 5 échecs, la falsification de `X-Forwarded-For`, le cookie `Secure`, la copie du jeton, les en-têtes, la clé JWT et les règles d'inscription.
