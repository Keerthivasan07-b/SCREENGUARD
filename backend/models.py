from typing import Literal, Optional, List
from pydantic import BaseModel, Field


class RegisterMessage(BaseModel):
    type: Literal["register"] = "register"
    role: Literal["student", "faculty"]
    studentId: Optional[str] = None
    studentName: Optional[str] = None
    facultyId: Optional[str] = None
    authToken: Optional[str] = None


class FrameMessage(BaseModel):
    type: Literal["frame"] = "frame"
    studentId: str
    timestamp: int
    encoding: str = "jpeg-base64"
    data: str


class AlertMessage(BaseModel):
    type: Literal["alert"] = "alert"
    studentId: str
    studentName: Optional[str] = None
    timestamp: int
    reason: str
    detail: str
    severity: str = "high"


class PingMessage(BaseModel):
    type: Literal["ping"] = "ping"
    studentId: str
    timestamp: Optional[int] = None


class StudentStatus(BaseModel):
    studentId: str
    studentName: str
    status: Literal["online", "offline", "slow"]


class RosterMessage(BaseModel):
    type: Literal["roster"] = "roster"
    students: List[StudentStatus]
