from fastapi import APIRouter

router = APIRouter(prefix="/auth", tags=["auth"])

@router.get("/test")
def test():
    return {"status": "auth router OK"}