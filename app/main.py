from fastapi import FastAPI
from app.api import users, food_items, orders

app = FastAPI(title="Canteen Management System")

app.include_router(users.router, prefix="/api")
app.include_router(food_items.router, prefix="/api")
app.include_router(orders.router, prefix="/api", tags=["Orders"]) 

@app.get("/")
def read_root():
    return {"message": "Welcome to the Canteen Management API!"}
