from html import escape

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.exc import IntegrityError

from app.core.admin import get_current_admin
from app.db.database import SessionLocal
from app.db.models import FridgeItemDB, UserDB
from app.web.layout import render_page

router = APIRouter()


def admin_guard(request: Request):
    try:
        return get_current_admin(request)
    except Exception:
        return None


@router.get("/admin", response_class=HTMLResponse)
def admin_dashboard(request: Request):
    admin = admin_guard(request)
    if not admin:
        return RedirectResponse("/", status_code=302)

    with SessionLocal() as db:
        users = db.query(UserDB).order_by(UserDB.id.asc()).all()
        fridge_items = db.query(FridgeItemDB).order_by(FridgeItemDB.id.desc()).all()
        user_by_id = {u.id: u.email for u in users}

        rows = []
        for user in users:
            admin_badge = '<span class="ml-2 rounded-full bg-emerald-100 px-2 py-1 text-xs font-bold text-emerald-800">ADMIN</span>' if user.is_admin else ''
            delete_button = '' if user.id == admin.id else f'''<form method="post" action="/admin/users/{user.id}/delete" onsubmit="return confirm('Supprimer ce compte et son contenu ?');"><button class="rounded-lg bg-red-600 px-3 py-2 text-sm font-semibold text-white hover:bg-red-700">Supprimer</button></form>'''
            rows.append(f'''
                <tr class="border-b border-slate-200 dark:border-slate-700">
                    <td class="px-4 py-3 font-semibold">{user.id}</td>
                    <td class="px-4 py-3">{escape(user.email)} {admin_badge}</td>
                    <td class="px-4 py-3">{user.age or '-'} / {user.weight or '-'} / {user.height or '-'}</td>
                    <td class="px-4 py-3">
                        <div class="flex flex-wrap gap-2">
                            <a href="/admin/users/{user.id}" class="rounded-lg bg-blue-600 px-3 py-2 text-sm font-semibold text-white hover:bg-blue-700">Modifier</a>
                            {delete_button}
                        </div>
                    </td>
                </tr>
            ''')

        item_rows = []
        for item in fridge_items:
            owner = escape(user_by_id.get(item.user_id, f'Utilisateur #{item.user_id}'))
            item_rows.append(f'''
                <tr class="border-b border-slate-200 dark:border-slate-700">
                    <td class="px-4 py-3">{item.id}</td>
                    <td class="px-4 py-3">{owner}</td>
                    <td class="px-4 py-3 font-semibold">{escape(item.name)}</td>
                    <td class="px-4 py-3">{item.quantity}</td>
                    <td class="px-4 py-3">{escape(item.expiration_date or '-')}</td>
                    <td class="px-4 py-3">
                        <form method="post" action="/admin/fridge/{item.id}/delete" onsubmit="return confirm('Supprimer cet élément ?');">
                            <button class="rounded-lg bg-red-600 px-3 py-2 text-sm font-semibold text-white hover:bg-red-700">Supprimer</button>
                        </form>
                    </td>
                </tr>
            ''')

    body = f'''
        <div class="flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
            <div>
                <div class="text-sm font-bold uppercase tracking-wider text-emerald-600">Administration</div>
                <h1 class="text-3xl font-black">Tableau de bord administrateur</h1>
                <p class="mt-1 text-slate-600 dark:text-slate-300">Connecté en tant que {escape(admin.email)}</p>
            </div>
            <a href="/" class="rounded-xl bg-slate-800 px-4 py-3 font-semibold text-white hover:bg-slate-900">Retour au site</a>
        </div>

        <section class="rounded-2xl bg-white p-6 shadow-sm dark:bg-slate-800">
            <div class="mb-4 flex items-center justify-between">
                <div><h2 class="text-xl font-black">Utilisateurs</h2><p class="text-sm text-slate-500 dark:text-slate-300">{len(users)} compte(s) enregistré(s)</p></div>
            </div>
            <div class="overflow-x-auto">
                <table class="min-w-full text-left text-sm">
                    <thead><tr class="border-b border-slate-300 dark:border-slate-600"><th class="px-4 py-3">ID</th><th class="px-4 py-3">Email</th><th class="px-4 py-3">Profil (âge / poids / taille)</th><th class="px-4 py-3">Actions</th></tr></thead>
                    <tbody>{''.join(rows) or '<tr><td colspan="4" class="px-4 py-6 text-center">Aucun utilisateur.</td></tr>'}</tbody>
                </table>
            </div>
        </section>

        <section class="rounded-2xl bg-white p-6 shadow-sm dark:bg-slate-800">
            <h2 class="text-xl font-black">Éléments des frigos</h2>
            <p class="mb-4 text-sm text-slate-500 dark:text-slate-300">Tu peux supprimer les produits ajoutés par les utilisateurs.</p>
            <div class="overflow-x-auto">
                <table class="min-w-full text-left text-sm">
                    <thead><tr class="border-b border-slate-300 dark:border-slate-600"><th class="px-4 py-3">ID</th><th class="px-4 py-3">Utilisateur</th><th class="px-4 py-3">Produit</th><th class="px-4 py-3">Qté</th><th class="px-4 py-3">Expiration</th><th class="px-4 py-3">Action</th></tr></thead>
                    <tbody>{''.join(item_rows) or '<tr><td colspan="6" class="px-4 py-6 text-center">Aucun élément.</td></tr>'}</tbody>
                </table>
            </div>
        </section>
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

        # Un administrateur ne peut pas se retirer lui-même ses droits depuis cette page.
        if user.id != admin.id:
            user.is_admin = 1 if form.get("is_admin") else 0

        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            return RedirectResponse(f"/admin/users/{user_id}?error=email_used", status_code=303)

    return RedirectResponse("/admin", status_code=303)


@router.post("/admin/users/{user_id}/delete")
def delete_user(user_id: int, request: Request):
    admin = admin_guard(request)
    if not admin:
        return RedirectResponse("/", status_code=302)
    if user_id == admin.id:
        return RedirectResponse("/admin", status_code=303)

    with SessionLocal() as db:
        user = db.query(UserDB).filter(UserDB.id == user_id).first()
        if user:
            db.query(FridgeItemDB).filter(FridgeItemDB.user_id == user_id).delete(synchronize_session=False)
            db.delete(user)
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
            db.delete(item)
            db.commit()

    return RedirectResponse("/admin", status_code=303)
