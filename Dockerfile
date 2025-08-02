FROM --platform=linux/amd64 python:3.12.3

WORKDIR /code

ENV PYTHONPATH=/code

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y libgl1


COPY ./app /code/app
COPY ./requirements.txt /code/requirements.txt
COPY ./pytest.ini /code/pytest.ini
COPY ./app/log_config.json /code/log_config.json
COPY ./macro-meals-mobile-d3f2c02bc942.json /code/macro-meals-mobile-d3f2c02bc942.json

# Install Python dependencies
RUN --mount=type=cache,target=/root/.cache \
    pip install -r requirements.txt


EXPOSE 8000 

CMD ["python", "app/main.py"]