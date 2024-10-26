import uvicorn
from fastapi import FastAPI

from calendar_sync_helper.routers.router_v1 import router as router_v1


def create_app():
    app = FastAPI()

    app.include_router(router_v1)
    app.include_router(router_v1, prefix="/v1")

    return app


app = create_app()

if __name__ == "__main__":  # For when running main.py in the debugger of an IDE
    uvicorn.run(app, host="0.0.0.0", port=8000)
