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
    username: str = Field(min_length=3, max_length=50)
    email: EmailStr
    password: str = Field(min_length=8, max_length=200)
    birthdate: Optional[str] = None
    address: Optional[AddressIn] = None
    billing: Optional[BillingIn] = None

class LoginIn(BaseModel):
    username: str
    password: str
    remember: bool = False
