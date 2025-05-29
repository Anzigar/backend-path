from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from database import get_db
from . import model, schema
from passlib.context import CryptContext

router = APIRouter(
    prefix="/users",
    tags=["users"]
)

contact_router = APIRouter(
    prefix="/contact",
    tags=["contact"]
)

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# User routes
@router.post("/", response_model=schema.UserResponse, status_code=status.HTTP_201_CREATED)
def create_user(user: schema.UserCreate, db: Session = Depends(get_db)):
    # Check if user with email already exists
    db_user_email = db.query(model.User).filter(model.User.email == user.email).first()
    if db_user_email:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    # Check if user with username already exists
    db_user_username = db.query(model.User).filter(model.User.username == user.username).first()
    if db_user_username:
        raise HTTPException(status_code=400, detail="Username already taken")
    
    # Create new user
    hashed_password = pwd_context.hash(user.password)
    db_user = model.User(
        username=user.username,
        email=user.email,
        password=hashed_password
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

@router.get("/{user_id}", response_model=schema.UserResponse)
def read_user(user_id: int, db: Session = Depends(get_db)):
    db_user = db.query(model.User).filter(model.User.id == user_id).first()
    if db_user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return db_user

# Contact form route
@contact_router.post("/", status_code=status.HTTP_201_CREATED, response_model=schema.ContactFormResponse)
def submit_contact_form(form_data: schema.ContactFormCreate, db: Session = Depends(get_db)):
    # Create a dict from the form data, filtering out None values
    form_dict = {k: v for k, v in form_data.dict().items() if v is not None}
    
    # Create new submission with only the provided data
    new_submission = model.ContactForm(**form_dict)
    
    db.add(new_submission)
    db.commit()
    db.refresh(new_submission)
    return new_submission
