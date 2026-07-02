from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from backend.database import engine, Base, seed_default_templates
from backend.services.logger import manager
from backend.routers import profile, search, jobs, applications, qa, logs, settings, bot, connections

# Initialize Database tables
Base.metadata.create_all(bind=engine)
seed_default_templates()


app = FastAPI(
    title="Auto J*b Applier API",
    description="100% Local, Self-Learning Job Application Assistant API",
    version="2.0.0"
)

# CORS Middleware config
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production/local deployment, restrict as needed. For dev, "*" is fine.
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

import os
from fastapi.staticfiles import StaticFiles

# Include Routers
app.include_router(profile.router)
app.include_router(search.router)
app.include_router(jobs.router)
app.include_router(applications.router)
app.include_router(qa.router)
app.include_router(logs.router)
app.include_router(settings.router)
app.include_router(bot.router)
app.include_router(connections.router)


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        # Loop to keep the connection alive and listen to incoming messages
        while True:
            data = await websocket.receive_json()
            # Handle client-initiated websocket messages (e.g. answering popups)
            if "type" in data:
                # We import it locally to prevent circular imports
                from backend.bot.popup_manager import handle_client_websocket_message
                await handle_client_websocket_message(data)
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception:
        manager.disconnect(websocket)

@app.get("/api/health")
def read_root():
    return {
        "app": "Auto J*b Applier",
        "status": "online",
        "documentation": "/docs"
    }

# Mount compiled React frontend static files
dist_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "frontend", "dist"))
if not os.path.exists(dist_path):
    # Fallback to check relative to root directory
    dist_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "frontend", "dist"))

if os.path.exists(dist_path):
    app.mount("/", StaticFiles(directory=dist_path, html=True), name="static")
