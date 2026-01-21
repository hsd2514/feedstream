from seed_data import SEED_IMAGES
from services.feed import store_image, add_images_tags, update_engagement
from services.redis import get_redis

def seed_database():
    from config import REDIS_HOST, REDIS_PORT, REDIS_DB
    
    print("Testing Redis connection...")
    print(f"Connecting to Redis at {REDIS_HOST}:{REDIS_PORT} (DB: {REDIS_DB})")
    
    redis = get_redis()
    if redis is None:
        print("Failed to create Redis client. Please check:")
        print("   1. Is Redis running? Try: redis-cli ping")
        print("   2. Check your .env file (REDIS_HOST, REDIS_PORT, REDIS_DB)")
        print(f"   Current settings: host={REDIS_HOST}, port={REDIS_PORT}, db={REDIS_DB}")
        return
    
    try:
        redis.ping()
        print(" Redis connection successful!")
    except Exception as e:
        print(f" Redis ping failed: {e}")
        print("\nTroubleshooting:")
        print("   1. Make sure Redis is running:")
        print("      Windows: Check if Redis service is running")
        print("      Or start Redis manually")
        print("   2. Verify connection settings in .env file")
        print("   3. Try connecting manually: redis-cli -h localhost -p 6379")
        return
    
    print("\nStarting database seeding...")
    
    for img in SEED_IMAGES:
        try:
            # Store image metadata
            store_image(img["image_id"], img["url"], img["tags"])
            
            # Add to tag index
            add_images_tags(img["image_id"], img["tags"])
            
            update_engagement(img["image_id"])
            
            print(f" Seeded {img['image_id']}")
        except Exception as e:
            print(f" Error seeding {img['image_id']}: {e}")
    
    print(f"\n Seeded {len(SEED_IMAGES)} images successfully!")

if __name__ == "__main__":
    seed_database()
