from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from typing import List
from datetime import datetime
from pydantic import BaseModel

from app.db.session import get_db
from app.db import models

router = APIRouter()

# ------------------------
# Schemas
# ------------------------
class OrderItemCreate(BaseModel):
    food_item_id: int
    quantity: int

class OrderCreate(BaseModel):
    user_id: int
    items: List[OrderItemCreate]

class InvoiceItem(BaseModel):
    food_item: str
    quantity: int
    unit_price: float
    subtotal: float

class Invoice(BaseModel):
    order_id: int
    customer_name: str
    total_items: int
    total_amount: float
    order_date: datetime
    items: List[InvoiceItem]

# ------------------------
# Create Order (bug-free version)
# ------------------------
@router.post("/orders/create", status_code=status.HTTP_201_CREATED, response_model=Invoice)
async def create_order(order: OrderCreate, db: AsyncSession = Depends(get_db)):
    # 1️⃣ Check if user exists
    result = await db.execute(select(models.User).where(models.User.id == order.user_id))
    user = result.scalars().first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    customer_name = user.name

    # 2️⃣ Fetch all food items at once
    food_ids = [item.food_item_id for item in order.items]
    if not food_ids:
        raise HTTPException(status_code=400, detail="Order must contain at least one item")

    result = await db.execute(select(models.FoodItem).where(models.FoodItem.id.in_(food_ids)))
    foods = {food.id: food for food in result.scalars().all()}

    # 3️⃣ Validate and build order items
    total_amount = 0.0
    order_items = []

    for item in order.items:
        food = foods.get(item.food_item_id)
        if not food:
            raise HTTPException(status_code=404, detail=f"Food item ID {item.food_item_id} not found")

        if food.stock <= 0:
            raise HTTPException(status_code=400, detail=f"'{food.name}' is out of stock")

        if item.quantity > food.stock:
            raise HTTPException(status_code=400, detail=f"Only {food.stock} units available for '{food.name}'")

        subtotal = food.price * item.quantity
        total_amount += subtotal

        # Update stock
        food.stock -= item.quantity
        db.add(food)

        order_items.append(models.OrderItem(
            food_item_id=item.food_item_id,
            quantity=item.quantity,
            item_price=food.price,
            total_price=subtotal
        ))

    # 4️⃣ Create order safely
    new_order = models.Order(
        user_id=order.user_id,
        total_amount=total_amount,
        created_at=datetime.utcnow(),
        order_items=order_items
    )

    db.add(new_order)
    await db.commit()  # commit once
    order_id = new_order.id  # safe to access now (expire_on_commit=False)

    # 5️⃣ Refetch order fully for invoice
    result = await db.execute(
        select(models.Order)
        .options(
            selectinload(models.Order.order_items).selectinload(models.OrderItem.food_item),
            selectinload(models.Order.user)
        )
        .where(models.Order.id == order_id)
    )
    full_order = result.scalars().first()

    if not full_order:
        raise HTTPException(status_code=500, detail="Order could not be loaded after creation")

    # 6️⃣ Build invoice
    invoice_items = [
        InvoiceItem(
            food_item=item.food_item.name,
            quantity=item.quantity,
            unit_price=item.item_price,
            subtotal=item.total_price
        )
        for item in full_order.order_items
    ]

    return Invoice(
        order_id=full_order.id,
        customer_name=full_order.user.name,
        total_items=len(full_order.order_items),
        total_amount=full_order.total_amount,
        order_date=full_order.created_at,
        items=invoice_items
    )

# ------------------------
# Get All Orders
# ------------------------
@router.get("/orders", response_model=List[Invoice])
async def get_all_orders(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(models.Order)
        .options(
            selectinload(models.Order.order_items).selectinload(models.OrderItem.food_item),
            selectinload(models.Order.user)
        )
    )
    orders = result.scalars().all()

    return [
        Invoice(
            order_id=o.id,
            customer_name=o.user.name,
            total_items=len(o.order_items),
            total_amount=o.total_amount,
            order_date=o.created_at,
            items=[
                InvoiceItem(
                    food_item=i.food_item.name,
                    quantity=i.quantity,
                    unit_price=i.item_price,
                    subtotal=i.total_price
                )
                for i in o.order_items
            ]
        )
        for o in orders
    ]

# ------------------------
# Get Order by ID
# ------------------------
@router.get("/orders/{order_id}", response_model=Invoice)
async def get_order(order_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(models.Order)
        .options(
            selectinload(models.Order.order_items).selectinload(models.OrderItem.food_item),
            selectinload(models.Order.user)
        )
        .where(models.Order.id == order_id)
    )
    order = result.scalars().first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    return Invoice(
        order_id=order.id,
        customer_name=order.user.name,
        total_items=len(order.order_items),
        total_amount=order.total_amount,
        order_date=order.created_at,
        items=[
            InvoiceItem(
                food_item=i.food_item.name,
                quantity=i.quantity,
                unit_price=i.item_price,
                subtotal=i.total_price
            )
            for i in order.order_items
        ]
    )
