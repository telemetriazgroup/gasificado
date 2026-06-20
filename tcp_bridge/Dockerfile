FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY bridge.py entrypoint.sh ./
RUN chmod +x entrypoint.sh

EXPOSE 9970 8081

ENTRYPOINT ["./entrypoint.sh"]
