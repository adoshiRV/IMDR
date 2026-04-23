"""Pydantic schemas for the shared vendor dimension."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

ALLOWED_VENDOR_TYPES = {"api", "file", "terminal"}


class VendorCreate(BaseModel):
    """Schema for creating a vendor dimension row."""

    vendor_code: str = Field(..., min_length=1, max_length=30)
    display_name: str = Field(..., min_length=1, max_length=50)
    vendor_type: str = Field(..., min_length=2, max_length=20)
    is_active: bool = True


class VendorResponse(VendorCreate):
    """Schema for returning a vendor dimension row."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    updated_at: datetime
