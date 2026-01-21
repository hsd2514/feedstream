from fastapi import FastAPI , HTTPException 
from services.redis import get_redis
from routes.feed import router as feed_router

app = FastAPI()

app.include_router(feed_router)

def main():
    app.run(host="0.0.0.0", port=8000)

@app.get("/")
async def root():
    return {"message": "Hello World"}

#health check
@app.get("/health")
async def health():
    return {"message": "OK"}

#health redis
@app.get("/health/redis")
async def health_redis():
    redis = get_redis()
    if redis is None:
        raise HTTPException(status_code=503, detail="Redis connection failed")
    return {"message": "Redis connection successful"}


if __name__ == "__main__":
    main()
