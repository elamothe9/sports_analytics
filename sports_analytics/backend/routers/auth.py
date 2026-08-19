from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter()


class LoginRequest(BaseModel):
    username: str = ""
    password: str = ""


@router.post("/login")
def login(body: LoginRequest):
    """
    Placeholder login — accepts any non-empty credentials.
    Accounts are not stored yet; the only failure case is a
    missing username or password.
    """
    username = body.username.strip()
    password = body.password.strip()

    if not username or not password:
        raise HTTPException(
            status_code=400,
            detail="Username and password are required",
        )

    return {
        "success": True,
        "username": username,
        "message": "Login successful",
    }
