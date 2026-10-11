FROM python:3.12-alpine

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /home/data

COPY IF.txt AlwaysRememberUsThisWay.txt scripts.py ./

RUN mkdir -p /home/data/output

CMD ["python", "/home/data/scripts.py"]