from typing import Literal

from pydantic import BaseModel, StrictBool, StrictInt, StrictStr

from app.modules.profile.schemas import DiagnosticProfile


class QuestionOption(BaseModel):
    # Strict: True no se serializa como 1, ni 4 como "4".
    code: StrictBool | StrictInt | StrictStr
    label: str


class Question(BaseModel):
    id: str
    text: str
    type: Literal["single", "multi"]
    options: list[QuestionOption]


class QuestionnaireResponse(BaseModel):
    questions: list[Question]


class CompleteDiagnosticResponse(BaseModel):
    profile: DiagnosticProfile
