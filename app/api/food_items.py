from fastapi import APIRouter, Depends, HTTPException, status, Response
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import func
from app.db.session import get_db
from app.db import models
from pydantic import BaseModel, Field
from typing import Optional

router = APIRouter()

# ------------------------
# Schemas
# ------------------------
class FoodItemCreate(BaseModel):
    name: str
    price: float
    category: str
    stock: int = Field(default=0, ge=0, description="Initial stock must be 0 or greater")

class FoodItemUpdate(BaseModel):
    name: Optional[str] = None
    price: Optional[float] = None
    category: Optional[str] = None
    stock: Optional[int] = Field(default=None, ge=0, description="Stock cannot be negative")

class FoodRestock(BaseModel):
    added_stock: int = Field(gt=0, description="Amount of stock to add (must be greater than 0)")

# ------------------------
# Create Food Item
# ------------------------
@router.post("/food_items", status_code=status.HTTP_201_CREATED)
async def create_food_item(food: FoodItemCreate, db: AsyncSession = Depends(get_db)):
    # Case-insensitive duplicate check
    result = await db.execute(
        select(models.FoodItem).where(func.lower(models.FoodItem.name) == food.name.lower())
    )
    existing = result.scalars().first()
    if existing:
        raise HTTPException(status_code=400, detail="Food item already exists")

    new_food = models.FoodItem(
        name=food.name.strip().title(),
        price=food.price,
        category=food.category.strip().title(),
        stock=food.stock
    )
    db.add(new_food)
    await db.commit()
    await db.refresh(new_food)

    headers = {"Location": f"/api/food_items/{new_food.id}"}
    return JSONResponse(
        status_code=status.HTTP_201_CREATED,
        content={
            "message": "Food item added successfully",
            "food_item": {
                "id": new_food.id,
                "name": new_food.name,
                "price": new_food.price,
                "category": new_food.category,
                "stock": new_food.stock
            },
        },
        headers=headers,
    )

# ------------------------
# Get All Food Items
# ------------------------
@router.get("/food_items", status_code=status.HTTP_200_OK)
async def get_food_items(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(models.FoodItem))
    food_items = result.scalars().all()
    return [
        {
            "id": item.id,
            "name": item.name,
            "price": item.price,
            "category": item.category,
            "stock": item.stock,
        }
        for item in food_items
    ]

# ------------------------
# Get Single Food Item
# ------------------------
@router.get("/food_items/{food_id}", status_code=status.HTTP_200_OK)
async def get_food_item(food_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(models.FoodItem).where(models.FoodItem.id == food_id))
    item = result.scalars().first()
    if not item:
        raise HTTPException(status_code=404, detail="Food item not found")

    return {
        "id": item.id,
        "name": item.name,
        "price": item.price,
        "category": item.category,
        "stock": item.stock,
    }

# ------------------------
# Update Food Item
# ------------------------
@router.patch("/food_items/{food_id}", status_code=status.HTTP_200_OK)
async def update_food_item(food_id: int, updates: FoodItemUpdate, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(models.FoodItem).where(models.FoodItem.id == food_id))
    food_item = result.scalars().first()
    if not food_item:
        raise HTTPException(status_code=404, detail="Food item not found")

    # Duplicate name check
    if updates.name:
        name_check = await db.execute(
            select(models.FoodItem).where(
                func.lower(models.FoodItem.name) == updates.name.lower(),
                models.FoodItem.id != food_id
            )
        )
        if name_check.scalars().first():
            raise HTTPException(status_code=400, detail="Another item with this name already exists")
        food_item.name = updates.name.strip().title()

    if updates.price is not None:
        food_item.price = updates.price

    if updates.category:
        food_item.category = updates.category.strip().title()

    if updates.stock is not None:
        if updates.stock < 0:
            raise HTTPException(status_code=400, detail="Stock cannot be negative")
        food_item.stock = updates.stock

    await db.commit()
    await db.refresh(food_item)

    return {
        "message": "Food item updated successfully",
        "food_item": {
            "id": food_item.id,
            "name": food_item.name,
            "price": food_item.price,
            "category": food_item.category,
            "stock": food_item.stock,
        },
    }

# ------------------------
# Restock Food Item
# ------------------------
@router.post("/food_items/restock/{food_id}", status_code=status.HTTP_200_OK)
async def restock_food_item(food_id: int, body: FoodRestock, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(models.FoodItem).where(models.FoodItem.id == food_id))
    item = result.scalars().first()
    if not item:
        raise HTTPException(status_code=404, detail="Food item not found")

    item.stock += body.added_stock
    await db.commit()
    await db.refresh(item)

    return {
        "message": f"Stock updated successfully (+{body.added_stock})",
        "food_item": {
            "id": item.id,
            "name": item.name,
            "price": item.price,
            "category": item.category,
            "stock": item.stock,
        },
    }

# ------------------------
# Delete Food Item
# ------------------------
@router.delete("/food_items/{food_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_food_item(food_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(models.FoodItem).where(models.FoodItem.id == food_id))
    item = result.scalars().first()
    if not item:
        raise HTTPException(status_code=404, detail="Food item not found")

    await db.delete(item)
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
