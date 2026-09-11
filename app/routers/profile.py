from fastapi import APIRouter
from app.models.profile import UserProfile

router = APIRouter(prefix="/profile", tags=["Profile"])

@router.post("/calculate")
def calculate_profile(data: UserProfile):

    if data.sex == "male":
        tmb = 10 * data.weight + 6.25 * data.height - 5 * data.age + 5
    else:
        tmb = 10 * data.weight + 6.25 * data.height - 5 * data.age - 161

    activity_factor = 1.4
    maintenance = tmb * activity_factor

    if data.objective == "lose":
        calories = maintenance - 300
    elif data.objective == "gain":
        calories = maintenance + 300
    else:
        calories = maintenance

    proteins = data.weight * 2.2
    fats = data.weight * 1
    carbs = (calories - (proteins * 4 + fats * 9)) / 4

    return {
        "tmb": round(tmb),
        "maintenance": round(maintenance),
        "calories_target": round(calories),
        "macros": {
            "proteins_g": round(proteins),
            "fats_g": round(fats),
            "carbs_g": round(carbs)
        }
    }
