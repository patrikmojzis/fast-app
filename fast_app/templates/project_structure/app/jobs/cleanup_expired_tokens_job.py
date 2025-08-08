from datetime import datetime, timedelta

from app.models.auth import Auth

# CRON JOB

class CleanupExpiredTokensJob():
    """
    Cron job to clean up expired refresh tokens from the database.
    
    This job should run daily to keep the database clean and performant.
    """
    
    async def run(self):
        """Remove expired refresh tokens from the database."""
        print("🧹 Starting cleanup of expired refresh tokens...")
        
        await Auth.cleanup_expired(grace_period_days=30)
        
        print("✅ Token cleanup completed successfully")