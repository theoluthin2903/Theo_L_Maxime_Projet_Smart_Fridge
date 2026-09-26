from html import escape

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from app.db.database import SessionLocal
from app.db.models import NotificationDB
from app.web.layout import render_page
from app.web.notifications import sync_notifications
from app.web.pages.fridge import get_user_id_from_cookie

router = APIRouter()


@router.get("/notifications", response_class=HTMLResponse)
def notifications_page(request: Request, view: str = "all"):
    user_id = get_user_id_from_cookie(request)
    if user_id is None:
        return RedirectResponse("/login", status_code=302)
    uid = int(user_id)
    sync_notifications(uid)
    with SessionLocal() as db:
        query = db.query(NotificationDB).filter(NotificationDB.user_id == uid)
        if view == "unread":
            query = query.filter(NotificationDB.is_read == 0)
        rows = query.order_by(NotificationDB.id.desc()).limit(100).all()
        unread = db.query(NotificationDB).filter(NotificationDB.user_id == uid, NotificationDB.is_read == 0).count()

    cards = ""
    for n in rows:
        state = "notification-card--read" if n.is_read else f"notification-card--{n.level}"
        action = "" if n.is_read else f'''<form method="post" action="/notifications/read"><input type="hidden" name="notification_id" value="{n.id}"><button class="notification-read-btn">✓ Marquer comme lue</button></form>'''
        cards += f'''<article class="notification-card {state}">
          <div class="notification-icon">{escape(n.icon or '🔔')}</div><div class="notification-content"><div class="notification-title-row"><h3>{escape(n.title)}</h3>{'<span class="notification-new">Nouveau</span>' if not n.is_read else '<span class="notification-read-label">Lue</span>'}</div>
          <p>{escape(n.message or '')}</p><div class="notification-footer"><time>{escape(n.created_at or '')}</time>{action}</div></div></article>'''
    if not cards:
        cards = '<div class="rounded-2xl border border-dashed border-slate-300 p-8 text-center text-slate-500">🔕 Aucune notification dans cette vue.</div>'
    body = f'''<section class="space-y-6">
      <div class="rounded-2xl border border-green-100 bg-white p-6 shadow-sm dark:border-slate-700 dark:bg-slate-800"><div class="flex flex-wrap items-center justify-between gap-4"><div><span class="recipe-tag recipe-tag--fridge">🔔 Notifications V2</span><h1 class="mt-3 text-3xl font-extrabold">Centre de notifications</h1><p class="mt-2 text-slate-500 dark:text-slate-300">Les alertes importantes restent ici jusqu'à ce que vous les ayez consultées.</p></div><div class="text-right"><div class="text-3xl font-black">{unread}</div><div class="text-sm text-slate-500">non lue(s)</div></div></div>
      <div class="mt-5 flex flex-wrap gap-2"><a class="notification-filter {'is-active' if view != 'unread' else ''}" href="/notifications">Toutes</a><a class="notification-filter {'is-active' if view == 'unread' else ''}" href="/notifications?view=unread">Non lues</a>{'<form method="post" action="/notifications/read-all"><button class="notification-filter">✓ Tout marquer comme lu</button></form>' if unread else ''}</div></div>
      <div class="notification-list">{cards}</div>
    </section>'''
    return render_page("Notifications", "/notifications", body, request)


@router.post("/notifications/read")
def read_notification(request: Request, notification_id: int = Form(...)):
    user_id = get_user_id_from_cookie(request)
    if user_id is not None:
        with SessionLocal() as db:
            row = db.query(NotificationDB).filter(NotificationDB.id == notification_id, NotificationDB.user_id == int(user_id)).first()
            if row:
                row.is_read = 1
                db.commit()
    return RedirectResponse("/notifications", status_code=303)


@router.post("/notifications/read-all")
def read_all_notifications(request: Request):
    user_id = get_user_id_from_cookie(request)
    if user_id is not None:
        with SessionLocal() as db:
            db.query(NotificationDB).filter(NotificationDB.user_id == int(user_id), NotificationDB.is_read == 0).update({NotificationDB.is_read: 1})
            db.commit()
    return RedirectResponse("/notifications", status_code=303)
