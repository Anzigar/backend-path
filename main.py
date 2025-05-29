from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
from config import API_PREFIX, DEBUG
from database import create_tables

# Import routers
from users.router import router as users_router
from users.router import contact_router
from newsEvents.router import news_router, event_router, category_router, tag_router, comment_router
from blog.router import blog_router, blog_category_router, newsletter_router
from storage.router import router as storage_router

# Create FastAPI instance with documentation configuration
app = FastAPI(
    title="Website Backend API",
    description="RESTful API for the Website with blog, news, events, and user management",
    version="1.0.0",
    openapi_url=f"{API_PREFIX}/openapi.json",
    docs_url=f"{API_PREFIX}/docs",
    redoc_url=f"{API_PREFIX}/redoc",
    debug=DEBUG
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, replace with specific origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include all routers with appropriate prefixes
# User and contact routes
app.include_router(users_router, prefix=f"{API_PREFIX}")
app.include_router(contact_router, prefix=f"{API_PREFIX}")

# News & Events routes
app.include_router(news_router, prefix=f"{API_PREFIX}")
app.include_router(event_router, prefix=f"{API_PREFIX}")
app.include_router(category_router, prefix=f"{API_PREFIX}")
app.include_router(tag_router, prefix=f"{API_PREFIX}")
app.include_router(comment_router, prefix=f"{API_PREFIX}")

# Blog routes
app.include_router(blog_router, prefix=f"{API_PREFIX}")
app.include_router(blog_category_router, prefix=f"{API_PREFIX}")
app.include_router(newsletter_router, prefix=f"{API_PREFIX}")

# Storage routes
app.include_router(storage_router, prefix=f"{API_PREFIX}")

# Root endpoint
@app.get("/")
async def root():
    return {
        "message": "Welcome to the Website API",
        "documentation": f"{API_PREFIX}/docs",
        "redoc": f"{API_PREFIX}/redoc"
    }

# Health check endpoint
@app.get("/health")
async def health_check():
    return {"status": "healthy"}

# Event handler to create database tables at startup
@app.on_event("startup")
async def startup_event():
    create_tables()
    print("Database tables created")

# Run the application
if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
