"""FastAPI 入口。"""
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import router
from app.settings import api_port, load_dotenv


@asynccontextmanager
async def lifespan(_app: FastAPI):
    load_dotenv()
    yield


def create_app() -> FastAPI:
    app = FastAPI(title="auto_download API", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(router)
    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn

    load_dotenv()
    uvicorn.run(
        "main_server:app",
        host="0.0.0.0",
        port=api_port(),
        reload=os.getenv("DOWNLOAD_API_RELOAD", "").lower() in ("1", "true", "yes"),
    )
