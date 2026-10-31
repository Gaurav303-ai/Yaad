"""Server-only Supabase admin client."""

from supabase import Client, create_client

from app.config import settings

supabase_admin: Client = create_client(settings.supabase_url, settings.supabase_secret_key)
