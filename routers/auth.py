from fastapi import APIRouter, FastAPI
from websockets import Router

router = APIRouter(prefix="/auth", tags=["auth"])

@router.get("/test")
def test():
    return {"status": "auth router ok"}

