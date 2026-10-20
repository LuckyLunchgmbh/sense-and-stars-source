"""Strict boundary validation; no client can smuggle roles or private flags."""
from datetime import date, datetime, time
from typing import Annotated, Literal
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


Name = Annotated[str, Field(min_length=1, max_length=150)]


class Login(StrictModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=False)
    email: Annotated[str, Field(min_length=3,max_length=254)]
    password: Annotated[str, Field(min_length=1,max_length=256)]

    @field_validator("email")
    @classmethod
    def normalize_email(cls,value):
        return value.strip()


class ProfileUpdate(StrictModel):
    tour_completed: bool


class ClientCreate(StrictModel):
    name: Name
    email: EmailStr
    birth_date: date | None = None
    birth_time: time | None = None
    birth_place: Annotated[str, Field(max_length=250)] | None = None
    themes: Annotated[list[Annotated[str, Field(min_length=1,max_length=150)]], Field(max_length=20)] = []

    @field_validator("birth_date")
    @classmethod
    def past_birth(cls, value):
        if value and (value > date.today() or value.year < 1900):
            raise ValueError("Geburtsdatum muss zwischen 1900 und heute liegen.")
        return value

    @field_validator("birth_time")
    @classmethod
    def local_time(cls, value):
        if value and value.tzinfo:
            raise ValueError("Uhrzeit als lokale Geburtszeit ohne Offset eingeben.")
        return value


class ClientUpdate(ClientCreate):
    name: Name | None = None
    email: EmailStr | None = None
    themes: list[Annotated[str, Field(min_length=1,max_length=150)]] | None = Field(default=None,max_length=20)
    chart_shared: bool | None = None


class PortalAccount(StrictModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=False)
    password: Annotated[str, Field(min_length=12,max_length=256)]


class ResourceCreate(StrictModel):
    kind: Literal["note", "task", "audio"]
    title: Name
    body: Annotated[str, Field(max_length=20000)] = ""
    shared: bool = False
    audio_url: Annotated[str, Field(max_length=2000)] | None = None

    @field_validator("audio_url")
    @classmethod
    def safe_url(cls,value):
        if value:
            parsed = urlparse(value)
            if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
                raise ValueError("Audio muss eine öffentliche HTTPS-Adresse ohne Zugangsdaten sein.")
        return value


class Share(StrictModel):
    shared: bool


class Booking(StrictModel):
    client_id: int = Field(gt=0)
    start_at: datetime
    title: Name
    duration_minutes: int = Field(default=60,ge=15,le=180)
    price_cents: int = Field(default=0,ge=0,le=1000000)

    @field_validator("start_at")
    @classmethod
    def aware(cls,value):
        if value.tzinfo is None:
            raise ValueError("Termin benötigt Zeitzone/UTC-Offset.")
        return value


class Prepare(StrictModel):
    acknowledged: Literal[True]


class AppointmentUpdate(StrictModel):
    status: Literal["completed", "cancelled"]


class ChartRequest(StrictModel):
    place_id: Annotated[str, Field(min_length=1,max_length=200)]
    fold: Literal[0,1] | None = None
