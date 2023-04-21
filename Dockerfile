FROM python:latest

RUN apt-get update && \
    apt-get install -y git gnupg curl coreutils

RUN pip install --upgrade pip && \
    pip install openai

RUN curl -sSL https://downloads.apache.org/age/KEYS | gpg --import

COPY compare.py .

CMD ["python", "compare.py"]