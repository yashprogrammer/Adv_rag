import uvicorn
from loguru import logger


def main() -> None:
    logger.info("Starting ADV RAG server")
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, workers=1, log_config=None)


if __name__ == "__main__":
    main()
