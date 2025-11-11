from sqlalchemy import Column, Integer, String, Float, ForeignKey, DateTime, Index, func, CheckConstraint
from sqlalchemy.orm import relationship
from datetime import datetime
from app.db.session import engine
from sqlalchemy.orm import DeclarativeBase
from app.db.base_class import Base


# Base class for all models
class Base(DeclarativeBase):
    pass


# -----------------------
# User
# -----------------------
class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    email = Column(String(100), unique=True, nullable=False)
    password = Column(String(100), nullable=False)
    role = Column(String(50), default="customer")
    orders = relationship("Order", back_populates="user")

# -----------------------
# FoodItem (Inventory)
# -----------------------
class FoodItem(Base):
    __tablename__ = "food_items"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    price = Column(Float, nullable=False)
    category = Column(String(50), nullable=False)
    stock = Column(Integer, nullable=False, default=0)
    order_items = relationship("OrderItem", back_populates="food_item")
    __table_args__ = (Index("ix_food_items_name_lower", func.lower(name), unique=True),)

# -----------------------
# Order
# -----------------------
class Order(Base):
    __tablename__ = "orders"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    total_amount = Column(Float, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    user = relationship("User", back_populates="orders")
    order_items = relationship("OrderItem", back_populates="order", cascade="all, delete-orphan")

# -----------------------
# Order Item Table
# -----------------------
class OrderItem(Base):
    __tablename__ = "order_items"

    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, ForeignKey("orders.id", ondelete="CASCADE"), nullable=False)
    food_item_id = Column(Integer, ForeignKey("food_items.id", ondelete="RESTRICT"), nullable=False)
    quantity = Column(Integer, nullable=False)
    item_price = Column(Float, nullable=False)  # store price at the time of order
    total_price = Column(Float, nullable=False)  # quantity * item_price

    order = relationship("Order", back_populates="order_items")  # <-- fixed
    food_item = relationship("FoodItem", back_populates="order_items")

    __table_args__ = (
        CheckConstraint("quantity > 0", name="check_quantity_positive"),
    )

    def __repr__(self):
        return (
            f"<OrderItem(id={self.id}, order_id={self.order_id}, "
            f"food_item_id={self.food_item_id}, quantity={self.quantity}, total={self.total_price})>"
        )
