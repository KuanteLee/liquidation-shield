# Start with python 3.11 image
FROM python:3.11-slim

# Copy the current directory into /app on the image
WORKDIR /app
COPY . /app

# Install package
RUN pip install -r requirements.txt

# 將 8080 埠暴露給外部
EXPOSE 8080

# Entry point command
CMD ["python", "main.py"]
