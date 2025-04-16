from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from typing import Callable
from starlette.middleware.base import BaseHTTPMiddleware
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.openapi.utils import get_openapi

from app.api.endpoints import meals, user, auth, macros, scan, location, billing
from app.core.config import settings

security_scheme = HTTPBearer()

def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema

    openapi_schema = get_openapi(
        title=settings.PROJECT_NAME,
        version="0.1.0",
        description="API for recommending meals from restaurants based on macro requirements and tracking nutrition",
        routes=app.routes,
    )

    openapi_schema["components"]["securitySchemes"] = {
        "bearerAuth": {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT"
        }
    }

    for path in openapi_schema["paths"].values():
        for method in path.values():
            if isinstance(method, dict):
                method.setdefault("security", [{"bearerAuth": []}])

    app.openapi_schema = openapi_schema
    return app.openapi_schema



app = FastAPI(
    title=settings.PROJECT_NAME,
    description="API for recommending meals from restaurants based on macro requirements",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    debug=settings.DEBUG,
)

@app.get("/docs", include_in_schema=False)
async def custom_swagger_ui_html():
    return get_swagger_ui_html(
        openapi_url="/openapi.json",
        title=f"{settings.PROJECT_NAME} - Swagger UI",
        oauth2_redirect_url="/docs/oauth2-redirect"
    )

app.openapi = custom_openapi

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(
    auth.router,
    prefix=f"{settings.API_V1_STR}/auth",
    tags=["authentication"],
)

app.include_router(
    scan.router,
    prefix=f"{settings.API_V1_STR}/scan",
    tags=["scan"],
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

app.include_router(
    location.router,
    prefix=f"{settings.API_V1_STR}/location",
    tags=["location"]
)

app.include_router(
    billing.router,
    prefix=f"{settings.API_V1_STR}/billing",
    tags=["billing"]
)


@app.get("/", tags=["status"])
async def root():
    return {"status": "online", "service": settings.PROJECT_NAME}


@app.exception_handler(Exception)
async def global_exception_handler(request: Request):
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