from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from app.web.data import get_nutrition_summary
from app.web.layout import require_auth, render_page

router = APIRouter()


@router.get("/nutrition", response_class=HTMLResponse)
def nutrition_page(request: Request):
    redirect = require_auth(request)
    if redirect:
        return redirect

    nutrition_summary = get_nutrition_summary()
    body = f"""
        <div class="rounded-2xl border border-green-100 bg-white p-6 shadow-sm">
            <h1 class="mb-5 text-3xl font-bold text-slate-800">Nutrition</h1>
            <div class="grid gap-4 md:grid-cols-4">
                <div class="rounded-xl border border-green-100 bg-green-50 p-4"><h3 class="text-lg font-semibold text-slate-800">Calories</h3><p class="mt-2 text-slate-600">{nutrition_summary['calories']} kcal</p></div>
                <div class="rounded-xl border border-green-100 bg-green-50 p-4"><h3 class="text-lg font-semibold text-slate-800">Protéines</h3><p class="mt-2 text-slate-600">{nutrition_summary['proteins']} g</p></div>
                <div class="rounded-xl border border-green-100 bg-green-50 p-4"><h3 class="text-lg font-semibold text-slate-800">Glucides</h3><p class="mt-2 text-slate-600">{nutrition_summary['carbs']} g</p></div>
                <div class="rounded-xl border border-green-100 bg-green-50 p-4"><h3 class="text-lg font-semibold text-slate-800">Lipides</h3><p class="mt-2 text-slate-600">{nutrition_summary['fat']} g</p></div>
            </div>
            <span class="mt-5 inline-block rounded-full bg-green-100 px-3 py-1 text-sm font-semibold text-green-800">Score global : {nutrition_summary['score']}</span>
        </div>
    """
    return render_page("Nutrition", "/nutrition", body, request)
