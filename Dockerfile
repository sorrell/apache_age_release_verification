FROM python:3.11

RUN apt-get update && \
    apt-get install -y git gnupg curl coreutils

RUN pip install --upgrade openai

RUN curl -sSL https://downloads.apache.org/age/KEYS | gpg --import

COPY compare.py .

CMD ["python", "compare.py"]
