from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from app.web.data import get_alerts
from app.web.layout import require_auth, render_page

router = APIRouter()


@router.get("/alerts", response_class=HTMLResponse)
def alerts_page(request: Request):
    redirect = require_auth(request)
    if redirect:
        return redirect

    items = "".join(
        f"""
        <li class="rounded-xl border border-amber-100 bg-amber-50 p-4">
            <strong class="block text-slate-800">{alert['title']}</strong>
            <div class="mt-1 text-sm text-slate-600">{alert['message']}</div>
        </li>
        """
        for alert in get_alerts()
    )
    body = f"""
        <div class="rounded-2xl border border-green-100 bg-white p-6 shadow-sm">
            <h1 class="mb-5 text-3xl font-bold text-slate-800">Alertes</h1>
            <ul class="space-y-3">{items}</ul>
        </div>
    """
    return render_page("Alertes", "/alerts", body, request)
