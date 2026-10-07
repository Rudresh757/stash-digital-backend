from __future__ import annotations

import re
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

Industry = Literal[
    "Medspa / aesthetic dermatology",
    "IV therapy",
    "Body contouring / weight loss",
    "Luxury used / CPO dealer",
    "Powersports dealer",
    "Other",
]
Country = Literal["USA", "Canada", "Australia", "Other"]
LeadStatus = Literal["new", "booked", "contacted"]

_PHONE_RE = re.compile(r"^[+()\-.\s\d]{7,20}$")


class LeadCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="ignore")

    name: str = Field(min_length=2, max_length=120)
    email: EmailStr
    phone: str | None = Field(default=None, max_length=32)
    business_name: str = Field(min_length=2, max_length=160)
    industry: Industry
    country: Country
    consent: bool
    source: str = Field(default="website", max_length=60)
    utm_source: str | None = Field(default=None, max_length=120)
    utm_medium: str | None = Field(default=None, max_length=120)
    utm_campaign: str | None = Field(default=None, max_length=120)
    website: str | None = Field(default=None, max_length=500)  # honeypot: must stay empty

    @field_validator("phone")
    @classmethod
    def _phone(cls, v: str | None) -> str | None:
        if not v:
            return None
        if not _PHONE_RE.match(v):
            raise ValueError("Enter a valid phone number.")
        return v

    @field_validator("consent")
    @classmethod
    def _consent(cls, v: bool) -> bool:
        if v is not True:
            raise ValueError("Consent is required.")
        return v


class LeadCreated(BaseModel):
    id: int
    message: str


class LeadAdmin(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    email: str
    phone: str | None
    business_name: str
    industry: str
    country: str
    consent: bool
    source: str
    utm_source: str | None
    utm_medium: str | None
    utm_campaign: str | None
    status: LeadStatus
    created_at: datetime


class LeadPage(BaseModel):
    items: list[LeadAdmin]
    total: int
    page: int
    page_size: int