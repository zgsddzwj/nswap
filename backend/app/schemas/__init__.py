from pydantic import BaseModel, Field


# ---------- auth ----------

class ProfileUpdate(BaseModel):
    nickname: str | None = Field(default=None, max_length=30)
    avatar_url: str | None = Field(default=None, max_length=500)
    unit: str | None = Field(default=None, max_length=20)


# ---------- community ----------

class JoinRequest(BaseModel):
    code: str = Field(min_length=4, max_length=20)


class ManualApplyRequest(BaseModel):
    building: str = Field(min_length=1, max_length=20)
    unit: str = Field(default="", max_length=20)
    proof_image: str = Field(min_length=1, max_length=500)


# ---------- items ----------

class ItemPayload(BaseModel):
    type: str = "sell"
    title: str = Field(min_length=1, max_length=60)
    description: str = Field(default="", max_length=1000)
    category: str = "other"
    condition: str | None = None
    price_cents: int | None = None
    negotiable: bool = False
    want_desc: str | None = Field(default=None, max_length=200)
    bid_cents: int | None = None
    images: list[str] = Field(default_factory=list, max_length=9)


# ---------- wants ----------

class WantCreate(BaseModel):
    message: str = Field(min_length=1, max_length=300)
    bid_cents: int | None = None
    swap_offer: str | None = Field(default=None, max_length=200)


class WantAction(BaseModel):
    action: str  # accept | reject


# ---------- messages ----------

class ContentPayload(BaseModel):
    content: str = Field(min_length=1, max_length=500)


class ItemMessageCreate(ContentPayload):
    content: str = Field(min_length=1, max_length=300)


# ---------- trades ----------

class ArrangeRequest(BaseModel):
    place_method: str  # face | porch | lobby
    meet_time: str
    place_note: str | None = Field(default=None, max_length=100)


class CancelRequest(BaseModel):
    reason: str = Field(default="", max_length=200)


class ReviewCreate(BaseModel):
    rating: int = Field(ge=1, le=3)
    content: str | None = Field(default=None, max_length=300)


class GratitudeCreate(BaseModel):
    content: str = Field(min_length=1, max_length=200)
    to_building: str | None = Field(default=None, max_length=20)


# ---------- reports / notifications ----------

class ReportCreate(BaseModel):
    target_type: str  # item | message | user
    target_id: int
    reason: str = Field(min_length=1, max_length=50)
    detail: str | None = Field(default=None, max_length=300)


class ReadRequest(BaseModel):
    ids: list[int]


class SubscribeRequest(BaseModel):
    template_key: str  # want | accepted | confirm | review
