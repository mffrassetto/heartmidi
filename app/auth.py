import os
from typing import Annotated
from fastapi import Header, HTTPException, Depends
from supabase import create_async_client, AsyncClient
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY")

if not SUPABASE_URL or not SUPABASE_ANON_KEY:
    raise ValueError("SUPABASE_URL e SUPABASE_ANON_KEY devem estar configurados no ambiente.")

supabase: AsyncClient = create_async_client(SUPABASE_URL, SUPABASE_ANON_KEY)

async def get_current_user(authorization: Annotated[str | None, Header()] = None):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=401, 
            detail="Token de autenticação ausente ou inválido"
        )
    
    token = authorization.split(" ")[1]
    try:
        # Valida o token com o Supabase Auth
        res = await supabase.auth.get_user(token)
        if not res.user:
            raise HTTPException(status_code=401, detail="Token inválido")
        return res.user
    except Exception as e:
        print(f"[AUTH ERROR] {str(e)}")
        raise HTTPException(status_code=401, detail="Falha na autenticação")

async def get_supabase_user_client(authorization: Annotated[str | None, Header()] = None):
    """
    Retorna um cliente Supabase configurado com o token do usuário.
    Isso garante que as políticas de RLS sejam aplicadas.
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Não autorizado")
    
    token = authorization.split(" ")[1]
    client = create_async_client(SUPABASE_URL, SUPABASE_ANON_KEY)
    client.postgrest.auth(token)
    return client
