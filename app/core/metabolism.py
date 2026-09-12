ACTIVITY_FACTORS = {
    "sedentary": 1.2,
    "light": 1.375,
    "moderate": 1.55,
    "intense": 1.725,
}

GOAL_ADJUSTMENTS = {
    "loss": -500,
    "gain": 300,
}


def compute_bmr_tdee(profile):
    if profile.sex == "male":
        bmr = 10 * profile.weight + 6.25 * profile.height - 5 * profile.age + 5
    else:
        bmr = 10 * profile.weight + 6.25 * profile.height - 5 * profile.age - 161

    activity_factor = ACTIVITY_FACTORS.get(profile.activity, ACTIVITY_FACTORS["sedentary"])
    tdee = bmr * activity_factor
    target_calories = max(1200, tdee + GOAL_ADJUSTMENTS.get(profile.goal, 0))

    proteins_g = profile.weight * 1.6
    fats_g = profile.weight * 0.8
    remaining = target_calories - (proteins_g * 4 + fats_g * 9)

    if remaining < 0:
        fats_g = max(0, (target_calories - proteins_g * 4) / 9)
        remaining = target_calories - (proteins_g * 4 + fats_g * 9)

    carbs_g = max(0, remaining / 4)

    return {
        "bmr": round(bmr),
        "tdee": round(tdee),
        "target_calories": round(target_calories),
        "macros": {
            "proteins_g": round(proteins_g),
            "fats_g": round(fats_g),
            "carbs_g": round(carbs_g),
        },
    }