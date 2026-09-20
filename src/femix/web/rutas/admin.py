from fastapi import APIRouter, Depends

from .auth import requerir_admin

router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(requerir_admin)])
