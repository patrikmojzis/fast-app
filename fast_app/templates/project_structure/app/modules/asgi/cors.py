import os

def get_cors_origins() -> list[str]:
    """Get CORS origins based on environment."""
    env = os.getenv("ENV")
    if env == "debug":
        return [
            # Add your CORS origins here
        ]
    elif env == "prod":
        return [
            # Add your CORS origins here
        ]
    elif env == "dev":
        return [
            # Add your CORS origins here
        ]
    else:
        raise ValueError("Invalid environment")