from fastapi import APIRouter, Depends, HTTPException
from typing import Dict, Any
from decimal import Decimal, ROUND_HALF_UP
from app.services.cache import get_revenue_summary
from app.core.auth import authenticate_request as get_current_user

router = APIRouter()

@router.get("/dashboard/summary")
async def get_dashboard_summary(
    property_id: str,
    month: int | None = None,
    year: int | None = None,
    current_user: dict = Depends(get_current_user)
) -> Dict[str, Any]:
    if (month is None) != (year is None):
        raise HTTPException(status_code=400, detail="month and year must be provided together")

    tenant_id = getattr(current_user, "tenant_id", None)
    if not tenant_id:
        raise HTTPException(status_code=401, detail="Tenant context is required")

    revenue_data = await get_revenue_summary(property_id, tenant_id, month=month, year=year)

    total_revenue = Decimal(str(revenue_data["total"]))
    display_total = total_revenue.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    
    return {
        "property_id": revenue_data["property_id"],
        "total_revenue": float(display_total),
        "total_revenue_exact": format(total_revenue, "f"),
        "currency": revenue_data["currency"],
        "reservations_count": revenue_data["count"],
    }
