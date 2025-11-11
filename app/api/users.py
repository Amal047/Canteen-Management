from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from app.db.session import get_db
from app.db import models
from pydantic import BaseModel
from enum import Enum

router = APIRouter()

class UserRole(str, Enum):
    admin = "admin"
    staff = "staff"
    customer = "customer"

class UserCreate(BaseModel):
    name: str
    email: str
    password: str
    role: UserRole = UserRole.customer



@router.post("/users", status_code=status.HTTP_201_CREATED)
async def create_user(user: UserCreate, db: AsyncSession = Depends(get_db)):
    # Check if user already exists
    result = await db.execute(select(models.User).where(models.User.email == user.email))
    existing_user = result.scalars().first()
    if existing_user:
        raise HTTPException(status_code=400, detail="Email already registered")

    # Create user
    new_user = models.User(
        name=user.name,
        email=user.email,
        password=user.password, 
        role=user.role
    )
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)

    headers = {"Location": f"/api/users/{new_user.id}"}
    response_data = {
        "message": "User created successfully",
        "user": {
            "id": new_user.id,
            "name": new_user.name,
            "email": new_user.email,
            "role": new_user.role
        }
    }
    return JSONResponse(status_code=status.HTTP_201_CREATED, content=response_data, headers=headers)


#get users
@router.get("/users", status_code=status.HTTP_200_OK)
async def get_users(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(models.User))
    users = result.scalars().all()

    response = [
        {
            "id": user.id,
            "name": user.name,
            "email": user.email,
            "role": user.role
        }
        for user in users
    ]
    return response
