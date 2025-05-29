from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from config import DATABASE_URL

print("Database URL is", DATABASE_URL)

# Configure engine based on database type
if DATABASE_URL.startswith('sqlite'):
    # SQLite specific configurations
    engine = create_engine(
        DATABASE_URL, 
        connect_args={"check_same_thread": False},
        echo=True  # Set to False in production
    )
else:
    # PostgreSQL or other database engine
    engine = create_engine(
        DATABASE_URL,
        echo=True  # Set to False in production
    )

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create base class for models
Base = declarative_base()

# Dependency to get DB session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Create all tables in the database
def create_tables():
    Base.metadata.create_all(bind=engine)
