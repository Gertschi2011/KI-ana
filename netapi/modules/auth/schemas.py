from pydantic import BaseModel, EmailStr, Field
from typing import Optional

class AddressIn(BaseModel):
    street: Optional[str] = ""
    zip: Optional[str] = ""
    city: Optional[str] = ""
    country: Optional[str] = ""

class BillingIn(BaseModel):
    company: Optional[str] = ""
    vat_id: Optional[str] = ""
    notes: Optional[str] = ""

class RegisterIn(BaseModel):
    name: Optional[str] = Field(default=None, max_length=120)
    username: str = Field(min_length=3, max_length=50)
    email: EmailStr
    # Password length policy is enforced in the /api/register route (configurable).
    password: str = Field(min_length=1, max_length=200)
    birthdate: Optional[str] = None
    address: Optional[AddressIn] = None
    billing: Optional[BillingIn] = None

class LoginIn(BaseModel):
    username: str
    password: str
    remember: bool = False
