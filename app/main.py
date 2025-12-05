import logging
import asyncio
import httpx
import time
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, Response
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from app.routes.v1_profile import router as profile_router
from app.routes.v1_generate import router as generate_router
from app.routes.v1_auth import router as auth_router
import os

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('umukozihr.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Auto-ping configuration to prevent Render free tier from sleeping
PING_INTERVAL = 240  # 4 minutes in seconds
SELF_PING_ENABLED = os.getenv("SELF_PING_ENABLED", "true").lower() == "true"

async def self_ping_task():
    """Background task that pings the server every 4 minutes to keep it alive on Render"""
    if not SELF_PING_ENABLED:
        logger.info("Self-ping disabled via SELF_PING_ENABLED environment variable")
        return

    # Get the service URL from environment or use localhost as fallback
    service_url = os.getenv("RENDER_EXTERNAL_URL", "http://localhost:8000")
    logger.info(f"Starting self-ping task - will ping {service_url}/health every {PING_INTERVAL} seconds")

    async with httpx.AsyncClient(timeout=10.0) as client:
        while True:
            try:
                await asyncio.sleep(PING_INTERVAL)
                response = await client.get(f"{service_url}/health")
                if response.status_code == 200:
                    logger.info(f"Self-ping successful: {response.json()}")
                else:
                    logger.warning(f"Self-ping returned status {response.status_code}")
            except Exception as e:
                logger.error(f"Self-ping failed: {e}")

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup/shutdown events"""
    # Startup
    logger.info("Starting UmukoziHR Resume Tailor API v1.3")

    # Start self-ping background task
    ping_task = asyncio.create_task(self_ping_task())

    yield

    # Shutdown
    logger.info("Shutting down UmukoziHR Resume Tailor API v1.3")
    ping_task.cancel()
    try:
        await ping_task
    except asyncio.CancelledError:
        pass

app = FastAPI(
    title="UmukoziHR Resume Tailor API",
    version="v1.3",
    lifespan=lifespan
)

# Add CORS middleware - get allowed origins from environment or use defaults
ALLOWED_ORIGINS = os.getenv(
    "ALLOWED_ORIGINS",
    "http://localhost:3000,http://127.0.0.1:3000,http://localhost:3001,http://127.0.0.1:3001"
).split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
logger.info(f"CORS middleware configured with origins: {ALLOWED_ORIGINS}")

# Request logging middleware
@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Log all incoming requests and responses"""
    start_time = time.time()

    # Log incoming request
    logger.info(f"Incoming request: {request.method} {request.url.path}")
    logger.info(f"Request headers: {dict(request.headers)}")
    logger.info(f"Request client: {request.client.host if request.client else 'unknown'}")

    # Process request
    try:
        response = await call_next(request)
        process_time = time.time() - start_time

        # Log response
        logger.info(f"Response: {response.status_code} for {request.method} {request.url.path} (took {process_time:.3f}s)")

        return response
    except Exception as e:
        logger.error(f"Request failed: {request.method} {request.url.path} - Error: {str(e)}", exc_info=True)
        raise

# Exception handlers
@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    """Log and handle HTTP exceptions"""
    logger.error(f"HTTP exception on {request.method} {request.url.path}: {exc.status_code} - {exc.detail}")
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail}
    )

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Log and handle validation errors"""
    logger.error(f"Validation error on {request.method} {request.url.path}: {exc.errors()}")
    return JSONResponse(
        status_code=422,
        content={"detail": exc.errors()}
    )

@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Log and handle all other exceptions"""
    logger.error(f"Unhandled exception on {request.method} {request.url.path}: {str(exc)}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"}
    )

app.include_router(auth_router)
app.include_router(profile_router, prefix="/api/v1/profile")
app.include_router(generate_router, prefix="/api/v1/generate")
logger.info("API routes registered successfully (v1.3 endpoints active)")

@app.get("/health")
def health_check():
    logger.info("Health check requested")
    return {"status": "healthy", "service": "umukozihrtailor-backend"}

ART = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "artifacts"))
os.makedirs(ART, exist_ok=True)
app.mount("/artifacts", StaticFiles(directory=ART), name="artifacts")
logger.info(f"Artifacts directory mounted at /artifacts: {ART}")
