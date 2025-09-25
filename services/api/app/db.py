import os
from typing import Generator
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base, Session

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./dev.db")

# Railway often provides a URL like "postgresql://...". We install psycopg (v3),
# so ensure SQLAlchemy uses the psycopg driver instead of psycopg2.
if DATABASE_URL.startswith("postgres://") and "+" not in DATABASE_URL:
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql+psycopg://", 1)
elif DATABASE_URL.startswith("postgresql://") and "+" not in DATABASE_URL:
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+psycopg://", 1)
elif "+psycopg2://" in DATABASE_URL:
    DATABASE_URL = DATABASE_URL.replace("+psycopg2://", "+psycopg://", 1)

# For Postgres via psycopg, the URL can be like:
# postgresql+psycopg://user:password@host:5432/dbname

# echo can be toggled with an env if you want SQL logs
engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
