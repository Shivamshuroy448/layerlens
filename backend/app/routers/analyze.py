from fastapi import APIRouter
from pydantic import BaseModel, Field

from .. import hf
from ..hf_schemas import AnalyzeResponse

router = APIRouter(prefix="/api/analyze", tags=["analyze"])


class AnalyzeRequest(BaseModel):
    model_id: str = Field(description="Bare HF id ('gpt2') or full huggingface.co URL")


@router.post("", response_model=AnalyzeResponse)
def analyze_model(req: AnalyzeRequest) -> AnalyzeResponse:
    """Resolve a Hugging Face model's true architecture (no weight download)."""
    return hf.analyze(req.model_id)
