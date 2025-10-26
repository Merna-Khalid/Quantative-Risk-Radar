
from threading import Lock

class Config:
    _instance = None
    _lock = Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance.MODEL_PATH = "models/hybrid_model.pkl"
                cls._instance.DB_URL = "sqlite:///data.db"
        return cls._instance
