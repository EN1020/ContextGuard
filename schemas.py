from pydantic import BaseModel, Field
from typing import List, Literal, Optional


class PromptInput(BaseModel):
    system_prompt: Optional[str] = Field(
        default="",
        description="System-level instruction"
    )
    user_prompt: str = Field(
        ...,
        description="User input prompt"
    )
    context: Optional[str] = Field(
        default="",
        description="External context or RAG content"
    )


class AnalysisResult(BaseModel):
    risk_level: Literal["LOW", "MEDIUM", "HIGH"]
    context_score: float = Field(
        ge=0.0,
        le=1.0,
        description="Completeness of provided context"
    )
    detected_issues: List[str]
    recommendations: List[str]


class AnalyzerResponse(BaseModel):
    input_summary: str
    analysis: AnalysisResult
