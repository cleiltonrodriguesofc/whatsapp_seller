from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from core.presentation.web.dependencies import templates

router = APIRouter(tags=["static"])

@router.get("/terms", response_class=HTMLResponse)
async def terms_page(request: Request):
    return templates.TemplateResponse(request=request, name="terms.html", context={"title": "Termos de Uso"})

@router.get("/privacy", response_class=HTMLResponse)
async def privacy_page(request: Request):
    return templates.TemplateResponse(request=request, name="privacy.html", context={"title": "Política de Privacidade"})

@router.get("/docs", response_class=HTMLResponse)
async def documentation_page(request: Request):
    return templates.TemplateResponse(request=request, name="documentation.html", context={"title": "Documentação"})
