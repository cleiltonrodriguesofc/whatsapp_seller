from fastapi import APIRouter, Depends, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from core.infrastructure.database.models import UserModel, ReferralCodeModel, ReferralConversionModel
from core.infrastructure.database.session import get_db
from core.presentation.web.dependencies import templates, login_required

router = APIRouter(tags=["referral"])

@router.get("/referral", response_class=HTMLResponse)
async def referral_dashboard(
    request: Request,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(login_required)
):
    # Fetch referral code
    ref_code_obj = db.query(ReferralCodeModel).filter(ReferralCodeModel.user_id == current_user.id).first()
    
    # Fetch conversions
    conversions = db.query(ReferralConversionModel).filter(ReferralConversionModel.referrer_id == current_user.id).all()
    
    # Calculate stats
    total_signups = len(conversions)
    total_converted = len([c for c in conversions if c.status in ("converted", "rewarded")])
    total_earned = sum([c.reward_brl for c in conversions if c.reward_brl])
    
    base_url = str(request.base_url).rstrip("/")
    ref_link = f"{base_url}/register?ref={ref_code_obj.code}" if ref_code_obj else "N/A"

    return templates.TemplateResponse(
        request=request, 
        name="referral_dashboard.html", 
        context={
            "user": current_user,
            "ref_code": ref_code_obj.code if ref_code_obj else "N/A",
            "ref_link": ref_link,
            "total_signups": total_signups,
            "total_converted": total_converted,
            "total_earned": total_earned,
            "conversions": conversions,
            "title": "Programa de Indicação"
        }
    )

@router.post("/referral/request-withdrawal")
async def request_withdrawal(
    pix_key: str = Form(...),
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(login_required)
):
    if current_user.referral_balance < 100:
        raise HTTPException(status_code=400, detail="Saldo insuficiente para saque (mínimo R$ 100,00).")
    
    # In a real app, we would create a WithdrawalRequest record
    # For this MVP, we'll just log it and reset the balance (simulating the request)
    current_user.referral_balance = 0
    db.commit()
    
    return RedirectResponse(url="/referral?success=withdraw_requested", status_code=303)
