from datetime import date, datetime, timedelta
from html import escape

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.exc import IntegrityError

from app.core.admin import get_current_admin
from app.core.security import hash_password
from app.db.database import SessionLocal
from app.db.models import AdminLogDB, FridgeItemDB, UserDB
from app.web.layout import render_page

router = APIRouter()


def log_action(db, admin_id: int, action: str, target: str = "", details: str = ""):
    db.add(AdminLogDB(
        admin_user_id=admin_id,
        action=action,
        target=target or None,
        details=details or None,
        created_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    ))


def admin_guard(request: Request):
    try:
        return get_current_admin(request)
    except Exception:
        return None


def parse_expiration(value):
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return None


def dashboard_data(users, fridge_items, logs):
    today = date.today()
    week_ago = today - timedelta(days=7)
    month_ago = today - timedelta(days=30)
    expired = 0
    expiring = 0
    categories = {}

    for item in fridge_items:
        d = parse_expiration(item.expiration_date)
        if d and d < today:
            expired += 1
        elif d and d <= today + timedelta(days=7):
            expiring += 1
        category = (item.category or "Sans catégorie").strip() or "Sans catégorie"
        categories[category] = categories.get(category, 0) + 1

    created_7 = sum(
        1 for log in logs
        if log.action == "Compte créé" and (lambda d: d is not None and d.date() >= week_ago)(parse_log_date(log.created_at))
    )
    created_30 = sum(
        1 for log in logs
        if log.action == "Compte créé" and (lambda d: d is not None and d.date() >= month_ago)(parse_log_date(log.created_at))
    )
    return expired, expiring, created_7, created_30, categories


def parse_log_date(value):
    try:
        return datetime.strptime(value, "%Y-%m-%d %H:%M:%S")
    except (TypeError, ValueError):
        return None


@router.get("/admin", response_class=HTMLResponse)
def admin_dashboard(request: Request):
    admin = admin_guard(request)
    if not admin:
        return RedirectResponse("/", status_code=302)

    with SessionLocal() as db:
        users = db.query(UserDB).order_by(UserDB.id.asc()).all()
        fridge_items = db.query(FridgeItemDB).order_by(FridgeItemDB.id.desc()).all()
        logs = db.query(AdminLogDB).order_by(AdminLogDB.id.desc()).limit(250).all()
        user_by_id = {u.id: u.email for u in users}

        expired, expiring, created_7, created_30, categories = dashboard_data(users, fridge_items, logs)
        total_users = len(users)
        total_admins = sum(bool(u.is_admin) for u in users)

        # Graphique simple : comptes créés par jour sur les 7 derniers jours.
        daily_counts = {today: 0 for today in [date.today() - timedelta(days=i) for i in range(6, -1, -1)]}
        for log in logs:
            if log.action != "Compte créé":
                continue
            d = parse_log_date(log.created_at)
            if d and d.date() in daily_counts:
                daily_counts[d.date()] += 1
        max_daily = max(daily_counts.values(), default=1) or 1
        graph = []
        for day, count in daily_counts.items():
            height = max(8, int((count / max_daily) * 120))
            graph.append(f'''<div class="admin-chart-col"><div class="admin-chart-value">{count}</div><div class="admin-chart-bar" style="height:{height}px"></div><small>{day.strftime('%d/%m')}</small></div>''')

        category_rows = []
        for name, count in sorted(categories.items(), key=lambda x: x[1], reverse=True)[:6]:
            pct = int((count / max(len(fridge_items), 1)) * 100)
            category_rows.append(f'''<div class="admin-progress-row"><div><span>{escape(name)}</span><strong>{count}</strong></div><div class="admin-progress"><span style="width:{pct}%"></span></div></div>''')

        rows = []
        for user in users:
            admin_badge = '<span class="ml-2 rounded-full bg-emerald-100 px-2 py-1 text-xs font-bold text-emerald-800">ADMIN</span>' if user.is_admin else ''
            delete_button = '' if user.id == admin.id else f'''<form method="post" action="/admin/users/{user.id}/delete" onsubmit="return confirm('Supprimer ce compte et son contenu ?');"><button class="rounded-lg bg-red-600 px-3 py-2 text-sm font-semibold text-white hover:bg-red-700">Supprimer</button></form>'''
            rows.append(f'''
                <tr class="border-b border-slate-200 dark:border-slate-700">
                    <td class="px-4 py-3 font-semibold">{user.id}</td>
                    <td class="px-4 py-3">{escape(user.email)} {admin_badge}</td>
                    <td class="px-4 py-3">{user.age or '-'} / {user.weight or '-'} / {user.height or '-'}</td>
                    <td class="px-4 py-3"><div class="flex flex-wrap gap-2"><a href="/admin/users/{user.id}" class="rounded-lg bg-blue-600 px-3 py-2 text-sm font-semibold text-white hover:bg-blue-700">Modifier</a>{delete_button}</div></td>
                </tr>
            ''')

        item_rows = []
        for item in fridge_items:
            owner = escape(user_by_id.get(item.user_id, f'Utilisateur #{item.user_id}'))
            d = parse_expiration(item.expiration_date)
            status = '<span class="admin-pill admin-pill--ok">OK</span>'
            if d and d < date.today():
                status = '<span class="admin-pill admin-pill--danger">Périmé</span>'
            elif d and d <= date.today() + timedelta(days=7):
                status = '<span class="admin-pill admin-pill--warning">Bientôt</span>'
            item_rows.append(f'''
                <tr class="border-b border-slate-200 dark:border-slate-700">
                    <td class="px-4 py-3">{item.id}</td><td class="px-4 py-3">{owner}</td><td class="px-4 py-3 font-semibold">{escape(item.name)}</td><td class="px-4 py-3">{item.quantity}</td><td class="px-4 py-3">{escape(item.expiration_date or '-')}</td><td class="px-4 py-3">{status}</td>
                    <td class="px-4 py-3"><form method="post" action="/admin/fridge/{item.id}/delete" onsubmit="return confirm('Supprimer cet élément ?');"><button class="rounded-lg bg-red-600 px-3 py-2 text-sm font-semibold text-white hover:bg-red-700">Supprimer</button></form></td>
                </tr>
            ''')

        recent_logs = logs[:15]
        log_rows = []
        for log in recent_logs:
            actor = "Système" if log.admin_user_id == 0 else escape(user_by_id.get(log.admin_user_id, f"Admin #{log.admin_user_id}"))
            log_rows.append(f'''<div class="admin-log"><div class="admin-log-icon">📝</div><div class="min-w-0 flex-1"><div class="flex flex-wrap items-center gap-2"><strong>{escape(log.action)}</strong><span class="text-xs text-slate-400">{escape(log.created_at)}</span></div><div class="text-sm text-slate-500 dark:text-slate-300">{escape(log.details or '')}</div><div class="text-xs text-slate-400">Par : {actor}</div></div></div>''')

        alerts = []
        if expired:
            alerts.append(f'<div class="admin-alert admin-alert--danger">🔴 <strong>{expired}</strong> produit(s) périmé(s)</div>')
        if expiring:
            alerts.append(f'<div class="admin-alert admin-alert--warning">⚠️ <strong>{expiring}</strong> produit(s) expirent dans les 7 jours</div>')
        if created_7:
            alerts.append(f'<div class="admin-alert admin-alert--info">👤 <strong>{created_7}</strong> nouveau(x) compte(s) cette semaine</div>')
        if not alerts:
            alerts.append('<div class="admin-alert admin-alert--success">✅ Aucun problème important détecté.</div>')

        body = f'''
        <div class="admin-hero">
          <div><div class="admin-kicker">SMART FRIDGE • ADMIN</div><h1>Centre d’administration</h1><p>Une interface organisée par onglets pour garder le dashboard clair et rapide à utiliser.</p></div>
          <a href="/" class="admin-btn admin-btn--light">← Retour au site</a>
        </div>

        <nav class="admin-tabs" aria-label="Navigation administration">
          <button type="button" class="admin-tab is-active" data-admin-tab="overview">🏠 Vue d’ensemble</button>
          <button type="button" class="admin-tab" data-admin-tab="users">👥 Utilisateurs</button>
          <button type="button" class="admin-tab" data-admin-tab="products">🥫 Aliments</button>
          <button type="button" class="admin-tab" data-admin-tab="stats">📊 Statistiques</button>
          <button type="button" class="admin-tab" data-admin-tab="logs">📝 Logs</button>
        </nav>

        <section class="admin-tab-panel is-active" data-admin-panel="overview">
          <div class="admin-stats">
            <div class="admin-stat"><span>👥</span><div><small>Utilisateurs</small><strong>{total_users}</strong><em>+{created_7} cette semaine</em></div></div>
            <div class="admin-stat"><span>🛡️</span><div><small>Administrateurs</small><strong>{total_admins}</strong></div></div>
            <div class="admin-stat"><span>🥫</span><div><small>Produits</small><strong>{len(fridge_items)}</strong></div></div>
            <div class="admin-stat admin-stat--warning"><span>⚠️</span><div><small>Bientôt périmés</small><strong>{expiring}</strong></div></div>
            <div class="admin-stat admin-stat--danger"><span>🔴</span><div><small>Périmés</small><strong>{expired}</strong></div></div>
          </div>
          <section class="admin-panel"><div class="admin-panel-head"><div><h2>🚨 Alertes & santé du système</h2><p>Les informations importantes à surveiller</p></div></div><div class="admin-alerts">{''.join(alerts)}</div></section>
          <section class="admin-panel"><div class="admin-panel-head"><div><h2>⚡ Actions rapides</h2><p>Accès direct aux différentes parties de l’administration</p></div></div><div class="admin-quick-actions"><button type="button" data-switch-tab="users">👥 Gérer les utilisateurs</button><button type="button" data-switch-tab="products">🥫 Gérer les aliments</button><button type="button" data-switch-tab="stats">📊 Voir les statistiques</button><button type="button" data-switch-tab="logs">📝 Voir les logs</button></div></section>
          <section class="admin-panel"><div class="admin-panel-head"><div><h2>🕐 Activité récente</h2><p>Les dernières actions enregistrées</p></div></div><div class="admin-log-list">{''.join(log_rows[:8]) or '<div class="text-slate-500">Aucune activité.</div>'}</div></section>
        </section>

        <section class="admin-tab-panel" data-admin-panel="users"><div class="admin-panel"><div class="admin-panel-head"><div><h2>👥 Utilisateurs</h2><p>{len(users)} compte(s) enregistré(s)</p></div></div><div class="overflow-x-auto"><table class="min-w-full text-left text-sm"><thead><tr class="border-b border-slate-300 dark:border-slate-600"><th class="px-4 py-3">ID</th><th class="px-4 py-3">Email</th><th class="px-4 py-3">Profil</th><th class="px-4 py-3">Actions</th></tr></thead><tbody>{''.join(rows) or '<tr><td colspan="4" class="px-4 py-6 text-center">Aucun utilisateur.</td></tr>'}</tbody></table></div></div></section>

        <section class="admin-tab-panel" data-admin-panel="products"><div class="admin-panel"><div class="admin-panel-head"><div><h2>🥫 Éléments des frigos</h2><p>État de chaque produit et suppression depuis l’administration.</p></div></div><div class="overflow-x-auto"><table class="min-w-full text-left text-sm"><thead><tr class="border-b border-slate-300 dark:border-slate-600"><th class="px-4 py-3">ID</th><th class="px-4 py-3">Utilisateur</th><th class="px-4 py-3">Produit</th><th class="px-4 py-3">Qté</th><th class="px-4 py-3">Expiration</th><th class="px-4 py-3">État</th><th class="px-4 py-3">Action</th></tr></thead><tbody>{''.join(item_rows) or '<tr><td colspan="7" class="px-4 py-6 text-center">Aucun élément.</td></tr>'}</tbody></table></div></div></section>

        <section class="admin-tab-panel" data-admin-panel="stats"><div class="admin-grid-2"><div class="admin-panel"><div class="admin-panel-head"><div><h2>📈 Créations de comptes</h2><p>7 derniers jours</p></div><strong>{created_30} / 30 jours</strong></div><div class="admin-chart">{''.join(graph)}</div></div><div class="admin-panel"><div class="admin-panel-head"><div><h2>🥫 Produits par catégorie</h2><p>Répartition actuelle</p></div></div>{''.join(category_rows) or '<p class="text-slate-500">Aucun produit.</p>'}</div></div><div class="admin-stats admin-stats--secondary"><div class="admin-stat"><span>📅</span><div><small>Nouveaux comptes / 7 jours</small><strong>{created_7}</strong></div></div><div class="admin-stat"><span>📆</span><div><small>Nouveaux comptes / 30 jours</small><strong>{created_30}</strong></div></div><div class="admin-stat"><span>📦</span><div><small>Catégories utilisées</small><strong>{len(categories)}</strong></div></div></div></section>

        <section class="admin-tab-panel" data-admin-panel="logs"><div class="admin-panel"><div class="admin-panel-head"><div><h2>📝 Journal d'activité</h2><p>Créations de comptes et actions administrateur les plus récentes.</p></div><strong>{len(logs)} événements chargés</strong></div><div class="admin-log-list">{''.join(log_rows) or '<div class="text-slate-500">Aucune activité.</div>'}</div></div></section>

        <script>
        (() => {{
          const tabs = document.querySelectorAll('[data-admin-tab]');
          const panels = document.querySelectorAll('[data-admin-panel]');
          function activate(name) {{
            tabs.forEach(tab => tab.classList.toggle('is-active', tab.dataset.adminTab === name));
            panels.forEach(panel => panel.classList.toggle('is-active', panel.dataset.adminPanel === name));
            history.replaceState(null, '', '#admin-' + name);
            window.scrollTo({{top: 0, behavior: 'smooth'}});
          }}
          tabs.forEach(tab => tab.addEventListener('click', () => activate(tab.dataset.adminTab)));
          document.querySelectorAll('[data-switch-tab]').forEach(button => button.addEventListener('click', () => activate(button.dataset.switchTab)));
          const initial = location.hash.startsWith('#admin-') ? location.hash.slice(7) : 'overview';
          if ([...tabs].some(tab => tab.dataset.adminTab === initial)) activate(initial);
        }})();
        </script>
        '''
        return render_page("Administration", "/admin", body, request)


@router.get("/admin/users/{user_id}", response_class=HTMLResponse)
def edit_user_page(user_id: int, request: Request):
    admin = admin_guard(request)
    if not admin:
        return RedirectResponse("/", status_code=302)
    with SessionLocal() as db:
        user = db.query(UserDB).filter(UserDB.id == user_id).first()
        if not user:
            return RedirectResponse("/admin", status_code=302)
        body = f'''
            <div class="flex items-center justify-between gap-4"><div><div class="text-sm font-bold uppercase tracking-wider text-emerald-600">Administration</div><h1 class="text-3xl font-black">Modifier l'utilisateur #{user.id}</h1></div><a href="/admin" class="rounded-xl bg-slate-800 px-4 py-3 font-semibold text-white">Retour</a></div>
            <form method="post" action="/admin/users/{user.id}/update" class="max-w-2xl space-y-5 rounded-2xl bg-white p-6 shadow-sm dark:bg-slate-800">
                <div><label class="mb-2 block font-semibold">Email</label><input name="email" type="email" required value="{escape(user.email)}" class="w-full rounded-xl border border-slate-300 p-3 dark:border-slate-600 dark:bg-slate-900" /></div>
                <div class="grid gap-4 sm:grid-cols-3"><div><label class="mb-2 block font-semibold">Âge</label><input name="age" type="number" value="{user.age or ''}" class="w-full rounded-xl border p-3 dark:bg-slate-900" /></div><div><label class="mb-2 block font-semibold">Poids</label><input name="weight" type="number" step="0.1" value="{user.weight or ''}" class="w-full rounded-xl border p-3 dark:bg-slate-900" /></div><div><label class="mb-2 block font-semibold">Taille</label><input name="height" type="number" step="0.1" value="{user.height or ''}" class="w-full rounded-xl border p-3 dark:bg-slate-900" /></div></div>
                <div class="grid gap-4 sm:grid-cols-2"><div><label class="mb-2 block font-semibold">Sexe</label><input name="sex" value="{escape(user.sex or '')}" class="w-full rounded-xl border p-3 dark:bg-slate-900" /></div><div><label class="mb-2 block font-semibold">Activité</label><input name="activity" value="{escape(user.activity or '')}" class="w-full rounded-xl border p-3 dark:bg-slate-900" /></div></div>
                <div><label class="mb-2 block font-semibold">Objectif</label><input name="goal" value="{escape(user.goal or '')}" class="w-full rounded-xl border p-3 dark:bg-slate-900" /></div>
                <label class="flex items-center gap-3"><input name="is_admin" type="checkbox" value="1" {'checked' if user.is_admin else ''} {'disabled' if user.id == admin.id else ''} class="h-5 w-5" /><span class="font-semibold">Compte administrateur</span></label>
                <button class="rounded-xl bg-emerald-600 px-5 py-3 font-bold text-white hover:bg-emerald-700">Enregistrer les modifications</button>
            </form>
            <div class="mt-8 border-t border-slate-200 pt-6 dark:border-slate-700"><h2 class="mb-1 text-xl font-black">🔑 Réinitialiser le mot de passe</h2><p class="mb-4 text-sm text-slate-500 dark:text-slate-300">Le mot de passe sera haché avant d'être enregistré.</p><form method="post" action="/admin/users/{user.id}/password" class="grid gap-4 md:grid-cols-2"><input name="password" type="password" minlength="6" required placeholder="Nouveau mot de passe" class="w-full rounded-xl border border-slate-300 p-3 dark:border-slate-600 dark:bg-slate-900" /><input name="password_confirm" type="password" minlength="6" required placeholder="Confirmer le mot de passe" class="w-full rounded-xl border border-slate-300 p-3 dark:border-slate-600 dark:bg-slate-900" /><button class="rounded-xl bg-slate-800 px-5 py-3 font-bold text-white hover:bg-slate-900 md:col-span-2">Réinitialiser</button></form></div>
        '''
    return render_page("Modifier utilisateur", "/admin", body, request)


@router.post("/admin/users/{user_id}/update")
async def update_user(user_id: int, request: Request):
    admin = admin_guard(request)
    if not admin:
        return RedirectResponse("/", status_code=302)
    form = await request.form()
    email = str(form.get("email", "")).strip().lower()
    if not email:
        return RedirectResponse(f"/admin/users/{user_id}?error=email", status_code=303)

    def number(name):
        value = str(form.get(name, "")).strip()
        return float(value) if value else None

    with SessionLocal() as db:
        user = db.query(UserDB).filter(UserDB.id == user_id).first()
        if not user:
            return RedirectResponse("/admin", status_code=303)
        duplicate = db.query(UserDB).filter(UserDB.email == email, UserDB.id != user_id).first()
        if duplicate:
            return RedirectResponse(f"/admin/users/{user_id}?error=email_used", status_code=303)
        user.email = email
        age = str(form.get("age", "")).strip()
        user.age = int(age) if age else None
        user.weight = number("weight")
        user.height = number("height")
        user.sex = str(form.get("sex", "")).strip() or None
        user.activity = str(form.get("activity", "")).strip() or None
        user.goal = str(form.get("goal", "")).strip() or None
        if user.id != admin.id:
            user.is_admin = 1 if form.get("is_admin") else 0
        log_action(db, admin.id, "Utilisateur modifié", f"#{user.id}", user.email)
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            return RedirectResponse(f"/admin/users/{user_id}?error=email_used", status_code=303)
    return RedirectResponse("/admin", status_code=303)


@router.post("/admin/users/{user_id}/password")
async def reset_user_password(user_id: int, request: Request):
    admin = admin_guard(request)
    if not admin:
        return RedirectResponse("/", status_code=302)
    form = await request.form()
    password = str(form.get("password", ""))
    confirmation = str(form.get("password_confirm", ""))
    if len(password) < 6 or password != confirmation:
        return RedirectResponse(f"/admin/users/{user_id}?error=password", status_code=303)
    with SessionLocal() as db:
        user = db.query(UserDB).filter(UserDB.id == user_id).first()
        if not user:
            return RedirectResponse("/admin", status_code=303)
        user.hashed_password = hash_password(password)
        log_action(db, admin.id, "Mot de passe réinitialisé", f"#{user.id}", user.email)
        db.commit()
    return RedirectResponse("/admin", status_code=303)


@router.post("/admin/users/{user_id}/delete")
def delete_user(user_id: int, request: Request):
    admin = admin_guard(request)
    if not admin or user_id == admin.id:
        return RedirectResponse("/", status_code=302) if not admin else RedirectResponse("/admin", status_code=303)
    with SessionLocal() as db:
        user = db.query(UserDB).filter(UserDB.id == user_id).first()
        if user:
            email = user.email
            db.query(FridgeItemDB).filter(FridgeItemDB.user_id == user_id).delete(synchronize_session=False)
            db.delete(user)
            log_action(db, admin.id, "Utilisateur supprimé", f"#{user_id}", email)
            db.commit()
    return RedirectResponse("/admin", status_code=303)


@router.post("/admin/fridge/{item_id}/delete")
def delete_fridge_item(item_id: int, request: Request):
    admin = admin_guard(request)
    if not admin:
        return RedirectResponse("/", status_code=302)
    with SessionLocal() as db:
        item = db.query(FridgeItemDB).filter(FridgeItemDB.id == item_id).first()
        if item:
            name = item.name
            db.delete(item)
            log_action(db, admin.id, "Produit supprimé", f"#{item_id}", name)
            db.commit()
    return RedirectResponse("/admin", status_code=303)
