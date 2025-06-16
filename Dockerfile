FROM --platform=linux/amd64 python:3.12.3

WORKDIR /code

ENV PYTHONPATH=/code

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PLAYWRIGHT_BROWSERS_PATH=/app/ms-playwright

# Install system dependencies for Playwright
RUN apt-get update && apt-get install -y \
    wget \
    libglib2.0-0 \
    libnss3 \
    libnspr4 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libdbus-1-3 \
    libxcb1 \
    libxkbcommon0 \
    libatspi2.0-0 \
    libx11-6 \
    libxcomposite1 \
    libxdamage1 \
    libxext6 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libpango-1.0-0 \
    libcairo2 \
    libasound2 \
    && rm -rf /var/lib/apt/lists/*

COPY ./app /code/app
COPY ./requirements.txt /code/requirements.txt
COPY ./pytest.ini /code/pytest.ini
COPY ./app/log_config.json /code/log_config.json
COPY ./macro-meals-mobile-d3f2c02bc942.json /code/macro-meals-mobile-d3f2c02bc942.json

# Install Python dependencies
RUN --mount=type=cache,target=/root/.cache \
    pip install -r requirements.txt

# Install Playwright browsers
RUN PLAYWRIGHT_BROWSERS_PATH=/app/ms-playwright python -m playwright install --with-deps chromium

EXPOSE 8000 

CMD ["python", "app/main.py"]