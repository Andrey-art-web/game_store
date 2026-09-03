from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

# Внутри Docker-сети контейнеры общаются по имени сервиса (game-db)
DATABASE_URL = "postgresql://postgres:password@game-db:5432/game_db"

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()