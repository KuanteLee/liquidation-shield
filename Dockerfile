# Start with python 3.11 image
FROM python:3.11-slim

# Copy the current directory into /app on the image
WORKDIR /app

# Ref: https://stackoverflow.com/questions/76945843/default-startup-tcp-probe-failed-1-time-consecutively-for-container-develop-on
ENV HOST 0.0.0.0

COPY . /app

# Install package
RUN pip install -r requirements.txt

# 將 8080 埠暴露給外部
EXPOSE 8080
ENV PORT 8080
# set hostname to localhost
ENV HOSTNAME "0.0.0.0"

# Entry point command
CMD ["python", "main.py"]
