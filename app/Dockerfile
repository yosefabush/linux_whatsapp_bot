FROM python:3.10-slim
WORKDIR /app
ENV VERIFY_TOKEN=${{secrets.VERIFY_TOKEN}}
ENV TOKEN=${{secrets.TOKEN}}
ENV NUMBER_ID_PROVIDER=${{secrets.PROVIDER_NUMBER}}
ENV PORT=5000
COPY . .
RUN pip install -r requirements.txt
CMD gunicorn --bind 0.0.0.0:5000 wsgi:app
