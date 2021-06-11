from typing import Optional, Any
from pydantic import BaseModel, Extra, Field
from .enums import ChatType, EntityType
from datetime import datetime

ChatPhoto = ChatLocation = ChatPermissions = Any


class APIModel(BaseModel):
    class Config:
        extra = Extra.allow


class User(APIModel):
    id: int
    is_bot: bool
    first_name: str
    last_name: Optional[str]
    username: Optional[str]
    language_code: Optional[str]
    can_join_groups: Optional[bool]
    can_read_all_group_messages: Optional[bool]
    supports_inline_queries: Optional[bool]


class Chat(APIModel):
    id: int
    type: ChatType
    title: Optional[str]
    username: Optional[str]
    first_name: Optional[str]
    last_name: Optional[str]
    photo: Optional[ChatPhoto]
    bio: Optional[str]
    description: Optional[str]
    invite_link: Optional[str]
    pinned_message: Optional[str]
    permissions: Optional[ChatPermissions]
    slow_mode_delay: Optional[int]
    message_auto_delete_time: Optional[int]
    sticker_set_name: Optional[str]
    can_set_sticker_set: Optional[bool]
    linked_chat_id: Optional[int]
    location: Optional[ChatLocation]


class Entity(APIModel):
    type: EntityType
    offset: int
    length: int
    url: Optional[str]
    user: Optional[User]
    language: Optional[str]

class Message(APIModel):
    text: Optional[str]
    chat: Chat
    entities: Optional[list[Entity]]
    message_id: int
    date: datetime
    edit_date: Optional[datetime]
    from_: User = Field(alias='from')

class Update(APIModel):
    message: Optional[Message]
    edited_message: Optional[Message]
