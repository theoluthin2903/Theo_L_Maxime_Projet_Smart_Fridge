from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.core.metabolism import compute_bmr_tdee
from app.db.database import get_db
from app.db.models import UserDB
from app.models.profile import ProfileUpdate

router = APIRouter(prefix="/profile", tags=["Profile"])


def _serialize(user: UserDB) -> dict:
    return {
        "age": user.age,
        "weight": user.weight,
        "height": user.height,
        "sex": user.sex,
        "activity": user.activity,
        "goal": user.goal,
    }


def _with_nutrition(user: UserDB) -> dict:
    data = _serialize(user)
    if all([user.age, user.weight, user.height, user.sex, user.activity, user.goal]):
        data["nutrition"] = compute_bmr_tdee(user)
    return data


@router.get("/me")
def get_my_profile(user: UserDB = Depends(get_current_user)):
    return _with_nutrition(user)


@router.put("/me")
def update_my_profile(
    data: ProfileUpdate,
    user: UserDB = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(user, field, value)

    db.add(user)
    db.commit()
    db.refresh(user)

    return _with_nutrition(user)