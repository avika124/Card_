from fastapi import APIRouter, Depends, HTTPException, Request

from core.database import authenticate_user, create_user, get_users, log_action
from python_fastapi.auth import create_token, get_current_user, require_roles, sanitize_user
from python_fastapi.schemas import LoginRequest, CreateUserRequest

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login")
def login(body: LoginRequest, request: Request):
    user = authenticate_user(body.email, body.password)
    if not user:
        raise HTTPException(401, "Invalid email or password.")
    log_action(user["id"], user["email"], "login", ip=request.client.host if request.client else "")
    return {"token": create_token(user), "user": sanitize_user(user)}


@router.post("/logout")
def logout(user: dict = Depends(get_current_user)):
    log_action(user["id"], user["email"], "logout")
    return {"ok": True}


@router.get("/me")
def me(user: dict = Depends(get_current_user)):
    return user


@router.get("/users")
def list_users(user: dict = Depends(get_current_user)):
    return {"users": get_users(user["company"])}


@router.post("/users")
def add_user(body: CreateUserRequest, user: dict = Depends(require_roles("admin"))):
    try:
        uid = create_user(body.email, body.name, body.role, user["company"], body.department, body.password)
    except Exception as e:
        raise HTTPException(400, f"Could not create user: {e}")
    log_action(user["id"], user["email"], "create_user", "user", uid, body.email)
    return {"id": uid}
