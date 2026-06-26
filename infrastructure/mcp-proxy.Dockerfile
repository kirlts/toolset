FROM python:3.11-alpine
COPY hindsight-mcp-proxy.py /app/proxy.py
EXPOSE 9090
CMD ["python3", "/app/proxy.py", "--port", "9090"]
