from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from typing import Callable
from starlette.middleware.base import BaseHTTPMiddleware
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from contextlib import asynccontextmanager
import uvicorn


from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.openapi.utils import get_openapi

from app.api.endpoints import (
    meals,
    user,
    auth,
    macros,
    scan,
    location,
    billing,
    products,
    notifications,
)
from app.core.config import settings
from app.tasks.macromeals_tasks import macromeals_tasks
import logging
import json

logger = logging.getLogger(__name__)

with open("app/log_config.json", "r") as file:
    LOGGING_CONFIG = json.load(file)

security_scheme = HTTPBearer()

scheduler = BackgroundScheduler()

# scheduled for midnight each day
scheduler.add_job(macromeals_tasks.downgrade_users, CronTrigger(hour="0"))

# scheduled for 8:00am each day
scheduler.add_job(
    macromeals_tasks.schedule_start_of_day_meal_reminders, CronTrigger(hour="8")
)

# scheduled for 8:10 AM daily
scheduler.add_job(
    macromeals_tasks.schedule_custom_meal_reminders_breakfast,
    CronTrigger(hour="8", minute="10"),
)

# scheduled for 12:00 PM daily
scheduler.add_job(
    macromeals_tasks.schedule_custom_meal_reminders_dinner,
    CronTrigger(hour="12"),
)

# scheduled for 5:00pm each day
scheduler.add_job(
    macromeals_tasks.schedule_end_of_day_meal_reminders, CronTrigger(hour="17")
)

# scheduled for 7:00 PM daily
scheduler.add_job(
    macromeals_tasks.schedule_custom_meal_reminders_dinner,
    CronTrigger(hour="19"),
)

# scheduled for 8:00 PM daily
scheduler.add_job(
    macromeals_tasks.trigger_macro_goal_completion_notification,
    CronTrigger(hour="20"),
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # start scheduler
    scheduler.start()
    yield
    # shut down scheduler
    scheduler.shutdown()


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
        "bearerAuth": {"type": "http", "scheme": "bearer", "bearerFormat": "JWT"}
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
    lifespan=lifespan,
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
    debug=settings.DEBUG,
)


@app.get("/docs", include_in_schema=False)
async def custom_swagger_ui_html():
    return get_swagger_ui_html(
        openapi_url="/openapi.json",
        title=f"{settings.PROJECT_NAME} - Swagger UI",
        oauth2_redirect_url="/docs/oauth2-redirect",
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
    location.router, prefix=f"{settings.API_V1_STR}/location", tags=["location"]
)

app.include_router(
    billing.router, prefix=f"{settings.API_V1_STR}/billing", tags=["billing"]
)

app.include_router(
    products.router, prefix=f"{settings.API_V1_STR}/products", tags=["products"]
)

app.include_router(
    notifications.router,
    prefix=f"{settings.API_V1_STR}/notifications",
    tags=["notifications"],
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
        log_config=LOGGING_CONFIG,
    )
