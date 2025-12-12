from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

from .routers.funds import router as funds_router
from .routers.trunk import router as trunk_router

app = FastAPI(
    title="Min-Trade V1 API",
    description="Fund allocation system with modular Tronc Commun and Cerveau Fondamental",
    version="1.1.0"
)

# Disable CORS. Do not remove this for full-stack development.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)

app.include_router(funds_router)
app.include_router(trunk_router)

@app.get("/healthz")
async def healthz():
    return {"status": "ok"}
