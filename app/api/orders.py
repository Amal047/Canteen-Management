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

@router.post("/orders/create", status_code=status.HTTP_201_CREATED, response_model=Invoice)
async def create_order(order: OrderCreate, db: AsyncSession = Depends(get_db)):
    # fetch user
    result = await db.execute(select(models.User).where(models.User.id == order.user_id))
    user = result.scalars().first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    customer_name = user.name

    # fetch food items
    food_ids = [item.food_item_id for item in order.items]
    result = await db.execute(select(models.FoodItem).where(models.FoodItem.id.in_(food_ids)))
    foods = {food.id: food for food in result.scalars().all()}

    # prepare order items
    order_items = []
    total_amount = 0
    for item in order.items:
        food = foods.get(item.food_item_id)
        if not food:
            raise HTTPException(status_code=404, detail=f"Food item id {item.food_item_id} not found")

        subtotal = food.price * item.quantity
        total_amount += subtotal

        order_items.append(models.OrderItem(
            food_item_id=item.food_item_id,
            quantity=item.quantity,
            item_price=food.price,
            total_price=subtotal
        ))

    # create order
    new_order = models.Order(
        user_id=order.user_id,
        total_amount=total_amount,
        created_at=datetime.utcnow(),
        order_items=order_items
    )

    db.add(new_order)
    await db.commit()

    # load items for invoice
    await db.refresh(new_order)
    await db.execute(
        select(models.Order)
        .options(selectinload(models.Order.order_items).selectinload(models.OrderItem.food_item))
        .where(models.Order.id == new_order.id)
    )

    invoice_items = [
        InvoiceItem(
            food_item=item.food_item.name,
            quantity=item.quantity,
            unit_price=item.item_price,
            subtotal=item.total_price
        )
        for item in new_order.order_items
    ]

    return Invoice(
        order_id=new_order.id,
        customer_name=customer_name,
        total_items=len(new_order.order_items),
        total_amount=total_amount,
        order_date=new_order.created_at,
        items=invoice_items
    )

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

    invoices = []
    for order in orders:
        invoice_items = [
            InvoiceItem(
                food_item=item.food_item.name,
                quantity=item.quantity,
                unit_price=item.item_price,
                subtotal=item.total_price
            )
            for item in order.order_items
        ]
        invoices.append(Invoice(
            order_id=order.id,
            customer_name=order.user.name,
            total_items=len(order.order_items),
            total_amount=order.total_amount,
            order_date=order.created_at,
            items=invoice_items
        ))

    return invoices

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

    invoice_items = [
        InvoiceItem(
            food_item=item.food_item.name,
            quantity=item.quantity,
            unit_price=item.item_price,
            subtotal=item.total_price
        )
        for item in order.order_items
    ]

    return Invoice(
        order_id=order.id,
        customer_name=order.user.name,
        total_items=len(order.order_items),
        total_amount=order.total_amount,
        order_date=order.created_at,
        items=invoice_items
    )
