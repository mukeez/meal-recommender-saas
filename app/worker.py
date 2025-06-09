from celery import Celery
from app.core.config import settings


# Initialize Celery app
broker_url = f'redis://{settings.REDIS_HOST}:{settings.REDIS_PORT}/0'

# Create Celery app
celery_app = Celery(
    'meal_recommender',
    broker=broker_url,
    backend=broker_url,
    include=['app.tasks.scraping_tasks']
)

celery_app.autodiscover_tasks(['app.tasks'])

# Configure Celery
celery_app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
    task_track_started=True,
    task_time_limit=600,  # 10 mins
)

if __name__ == '__main__':
    celery_app.start()