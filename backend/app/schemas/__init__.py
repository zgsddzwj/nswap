from pydantic import BaseModel, Field


# ---------- auth ----------

class LoginRequest(BaseModel):
    """登录请求：带 code=自建服务器模式（wx.login 换 token）；不带=请求头注入身份。"""

    code: str | None = Field(default=None, max_length=128)


class ProfileUpdate(BaseModel):
    nickname: str | None = Field(default=None, max_length=30)
    avatar_url: str | None = Field(default=None, max_length=500)
    unit: str | None = Field(default=None, max_length=20)


class ContactSettings(BaseModel):
    """联系方式设置：用户主动填写，contact_enabled 才会对交易对方开放交换。"""

    contact_enabled: bool = False
    contact_wechat: str = Field(default="", max_length=64)
    contact_phone: str = Field(default="", max_length=20)


# ---------- community ----------

class JoinRequest(BaseModel):
    code: str = Field(min_length=4, max_length=20)


class ManualApplyRequest(BaseModel):
    community_id: int  # 申请加入的小区（人工审核通道，docs/07 §4.2）
    building: str = Field(min_length=1, max_length=20)
    unit: str = Field(default="", max_length=20)
    proof_image: str = Field(min_length=1, max_length=500)


# ---------- items ----------

class ItemPayload(BaseModel):
    type: str = "sell"
    title: str = Field(min_length=1, max_length=60)
    description: str = Field(default="", max_length=1000)
    category: str | None = None  # None/非法值 = 按标题自动识别（docs/11）
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
    # 换物意向附图（我方交换物的照片，≤3 张，公网上传 URL；仅物品方可见）
    images: list[str] = Field(default_factory=list, max_length=3)


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


# ---------- 管理后台 JSON API（docs/08 §4） ----------

class AdminLoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=30)
    password: str = Field(min_length=1, max_length=100)


class AdminInviteCreateRequest(BaseModel):
    building: str = Field(min_length=1, max_length=20)
    count: int = Field(default=10, ge=1, le=100)
    days: int = Field(default=14, ge=1, le=90)
    batch_note: str = Field(default="", max_length=100)
    community_id: int | None = None  # 仅超管生效


class AdminAnnouncementCreateRequest(BaseModel):
    title: str = Field(min_length=1, max_length=100)
    content: str = Field(min_length=1, max_length=5000)
    community_id: int | None = None  # 仅超管生效


class AdminAnnouncementUpdateRequest(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=100)
    content: str | None = Field(default=None, min_length=1, max_length=5000)
    pinned: bool | None = None


class AdminReportHandleRequest(BaseModel):
    decision: str  # resolve | dismiss
    apply_action: bool = False
    note: str = Field(default="", max_length=200)


class AdminFaqCreateRequest(BaseModel):
    title: str = Field(min_length=1, max_length=50)
    content: str = Field(min_length=1, max_length=2000)
    pinned: bool = False
    community_id: int | None = None  # 仅超管生效


class AdminFaqUpdateRequest(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=50)
    content: str | None = Field(default=None, min_length=1, max_length=2000)
    pinned: bool | None = None


class AdminCommunityCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=50)
    city: str = Field(min_length=1, max_length=50)
    district: str = Field(default="", max_length=50)
    address: str = Field(default="", max_length=200)
    admin_username: str = Field(min_length=3, max_length=30)
    admin_name: str = Field(default="", max_length=30)
    admin_password: str = Field(min_length=8, max_length=64)


class AdminPasswordChangeRequest(BaseModel):
    old_password: str = Field(min_length=1, max_length=100)
    new_password: str = Field(min_length=8, max_length=64)


class AdminVerifyRejectRequest(BaseModel):
    note: str = Field(default="", max_length=200)
