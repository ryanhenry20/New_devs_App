from datetime import datetime
from decimal import Decimal
from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)


def _get_month_bounds(year: int, month: int) -> tuple[datetime, datetime]:
    start_date = datetime(year, month, 1)
    if month < 12:
        end_date = datetime(year, month + 1, 1)
    else:
        end_date = datetime(year + 1, 1, 1)
    return start_date, end_date


async def _fetch_revenue_summary(
    property_id: str,
    tenant_id: str,
    month: Optional[int] = None,
    year: Optional[int] = None,
    db_session=None,
) -> Dict[str, Any]:
    from sqlalchemy import text
    from app.core.database_pool import db_pool

    if (month is None) != (year is None):
        raise ValueError("month and year must be provided together")

    if not db_pool.session_factory:
        await db_pool.initialize()

    if not db_pool.session_factory:
        raise RuntimeError("Database pool is not available")

    session_context = db_session or db_pool.get_session()
    params: Dict[str, Any] = {
        "property_id": property_id,
        "tenant_id": tenant_id,
    }

    filters = ""
    if month is not None and year is not None:
        start_date, end_date = _get_month_bounds(year, month)
        params["start_date"] = start_date
        params["end_date"] = end_date
        filters = """
            AND (r.check_in_date AT TIME ZONE p.timezone) >= :start_date
            AND (r.check_in_date AT TIME ZONE p.timezone) < :end_date
        """

    query = text(f"""
        SELECT 
            r.property_id,
            COALESCE(SUM(r.total_amount), 0) as total_revenue,
            COUNT(r.id) as reservation_count,
            COALESCE(MIN(r.currency), 'USD') as currency
        FROM reservations r
        JOIN properties p
          ON p.id = r.property_id
         AND p.tenant_id = r.tenant_id
        WHERE r.property_id = :property_id
          AND r.tenant_id = :tenant_id
          {filters}
        GROUP BY r.property_id
    """)

    async with session_context as session:
        result = await session.execute(query, params)
        row = result.fetchone()

    if row:
        total_revenue = Decimal(str(row.total_revenue))
        return {
            "property_id": property_id,
            "tenant_id": tenant_id,
            "total": str(total_revenue),
            "currency": row.currency,
            "count": row.reservation_count,
        }

    return {
        "property_id": property_id,
        "tenant_id": tenant_id,
        "total": "0.00",
        "currency": "USD",
        "count": 0,
    }

async def calculate_monthly_revenue(
    property_id: str,
    month: int,
    year: int,
    tenant_id: Optional[str] = None,
    db_session=None,
) -> Decimal:
    """
    Calculates revenue for a specific month using the property's local timezone.
    """
    if not tenant_id:
        raise ValueError("tenant_id is required for monthly revenue calculations")

    summary = await _fetch_revenue_summary(
        property_id=property_id,
        tenant_id=tenant_id,
        month=month,
        year=year,
        db_session=db_session,
    )
    return Decimal(summary["total"])


async def calculate_total_revenue(
    property_id: str,
    tenant_id: str,
    month: Optional[int] = None,
    year: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Aggregates revenue from database.
    """
    try:
        return await _fetch_revenue_summary(
            property_id=property_id,
            tenant_id=tenant_id,
            month=month,
            year=year,
        )
    except Exception as e:
        logger.exception(
            "Database error while calculating revenue for property %s (tenant: %s)",
            property_id,
            tenant_id,
        )
        raise
