from fastapi import APIRouter, HTTPException
from services.stats import get_leaders

router = APIRouter()


@router.get("/leaders")
def leaders():
    try:
        data = get_leaders()
        return data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))