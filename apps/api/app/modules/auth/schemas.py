import uuid
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, StrictBool


class ProgramOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    code: str
    name: str


class RegisterRequest(BaseModel):
    # Los campos son opcionales a propósito: el servicio valida y acumula los errores
    # de negocio (NICKNAME_LENGTH, PROGRAM_REQUIRED, ...) en una sola respuesta.
    nickname: str | None = Field(default=None, max_length=200)
    email: str | None = Field(default=None, max_length=320)
    password: str | None = Field(default=None, max_length=1024)
    program_code: str | None = Field(default=None, max_length=50)
    accepted_terms: StrictBool | None = None


class RegisterResponse(BaseModel):
    status: Literal["pending_verification"] = "pending_verification"


class VerifyEmailRequest(BaseModel):
    token: str = Field(min_length=1, max_length=256)


class VerifiedUserOut(BaseModel):
    id: uuid.UUID
    nickname: str
    program: ProgramOut


class VerifyEmailResponse(BaseModel):
    user: VerifiedUserOut
    next: Literal["onboarding"] = "onboarding"


class ResendVerificationRequest(BaseModel):
    email: str | None = Field(default=None, max_length=320)


class ResendVerificationResponse(BaseModel):
    status: Literal["accepted"] = "accepted"
    message: str = "Si hay una cuenta pendiente de verificación con ese correo, te enviamos un nuevo enlace."
