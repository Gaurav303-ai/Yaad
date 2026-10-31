"""Server-only asynchronous Supabase admin client factory."""

from supabase import AsyncClient, acreate_client

from app.config import settings


async def create_supabase_admin() -> AsyncClient:
    """Create an admin client using the server-only secret key."""
    return await acreate_client(settings.supabase_url, settings.supabase_secret_key)
