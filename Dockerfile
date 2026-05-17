FROM python:3.10-slim

WORKDIR /app

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p uploads config logs ssl img

EXPOSE 8080 8443 5001 5002 21 445

EXPOSE 50000-50050

VOLUME ["/app/uploads", "/app/config", "/app/logs", "/app/ssl","/app/img"]

CMD ["python", "app.py"]