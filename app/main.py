"""Main module for the meal recommendation API.

This module initializes the FastAPI application and includes all routes.
"""
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from typing import Callable
from starlette.middleware.base import BaseHTTPMiddleware



# Create FastAPI app
from app.api.endpoints import meals, user, auth, macros
from app.core.config import settings

app = FastAPI(
    title=settings.PROJECT_NAME,
    description="API for recommending meals from restaurants based on macro requirements",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    debug=settings.DEBUG,
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Adjust this in production to specific origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(
    auth.router,
    prefix=f"{settings.API_V1_STR}/auth",
    tags=["authentication"],
)

app.include_router(
    macros.router,
    prefix=f"{settings.API_V1_STR}/macros",
    tags=["macros"],
)

app.include_router(
    user.router,
    prefix=f"{settings.API_V1_STR}/user",
    tags=["user"],
)

app.include_router(
    meals.router,
    prefix=f"{settings.API_V1_STR}/meals",
    tags=["meals"],
)


@app.get("/", tags=["status"])
async def root():
    """Root endpoint to check API status."""
    return {"status": "online", "service": settings.PROJECT_NAME}


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global exception handler for unhandled exceptions."""
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error", "path": str(request.url)},
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG,
    )


@app.get("/", tags=["status"])
async def root():
    """Root endpoint to check API status."""
    return {"status": "online", "service": settings.PROJECT_NAME}


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global exception handler for unhandled exceptions."""
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error", "path": str(request.url)},
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG,
    )