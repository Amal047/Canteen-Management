from fastapi import APIRouter, Depends, HTTPException, status, Response
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import func
from app.db.session import get_db
from app.db import models
from pydantic import BaseModel
from typing import Optional


router = APIRouter()

# schema
class FoodItemCreate(BaseModel):
    name: str
    price: float
    category: str
    
class FoodItemUpdate(BaseModel):
    name: Optional[str] = None
    price: Optional[float] = None
    category: Optional[str] = None

#Create food item
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
        name=food.name.strip().title(),  # Normalize name
        price=food.price,
        category=food.category.strip().title()
    )
    db.add(new_food)
    await db.commit()
    await db.refresh(new_food)

    headers = {"Location": f"/api/food_items/{new_food.id}"}
    response_data = {
        "message": "Food item added successfully",
        "food_item": {
            "id": new_food.id,
            "name": new_food.name,
            "price": new_food.price,
            "category": new_food.category
        }
    }
    return JSONResponse(status_code=status.HTTP_201_CREATED, content=response_data, headers=headers)


# Get all food items
@router.get("/food_items", status_code=status.HTTP_200_OK)
async def get_food_items(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(models.FoodItem))
    food_items = result.scalars().all()
    return [
        {
            "id": item.id,
            "name": item.name,
            "price": item.price,
            "category": item.category
        }
        for item in food_items
    ]


# Get single food item
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
        "category": item.category
    }

# patch food items
@router.patch("/food_items/{food_id}", status_code=status.HTTP_200_OK)
async def update_food_item(food_id: int, updates: FoodItemUpdate, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(models.FoodItem).where(models.FoodItem.id == food_id))
    food_item = result.scalars().first()

    if not food_item:
        raise HTTPException(status_code=404, detail="Food item not found")

    # Case-insensitive name check if name is being updated
    if updates.name:
        name_check = await db.execute(
            select(models.FoodItem).where(func.lower(models.FoodItem.name) == updates.name.lower(),
                                          models.FoodItem.id != food_id)
        )
        if name_check.scalars().first():
            raise HTTPException(status_code=400, detail="Another item with this name already exists")

        food_item.name = updates.name.strip().title()

    if updates.price is not None:
        food_item.price = updates.price

    if updates.category:
        food_item.category = updates.category.strip().title()

    await db.commit()
    await db.refresh(food_item)

    return {
        "message": "Food item updated successfully",
        "food_item": {
            "id": food_item.id,
            "name": food_item.name,
            "price": food_item.price,
            "category": food_item.category
        }
    }

# Delete food item
@router.delete("/food_items/{food_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_food_item(food_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(models.FoodItem).where(models.FoodItem.id == food_id))
    item = result.scalars().first()
    if not item:
        raise HTTPException(status_code=404, detail="Food item not found")

    await db.delete(item)
    await db.commit()

    return Response(status_code=status.HTTP_204_NO_CONTENT)
