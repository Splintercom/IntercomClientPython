FROM astral/uv:python3.12-bookworm-slim

COPY . /mnt/build
WORKDIR /mnt/build

RUN uv sync

CMD [ "uv", "run", "python", "main.py"]