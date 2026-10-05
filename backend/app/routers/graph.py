from fastapi import APIRouter, HTTPException

from ..demo_graphs import DEMOS
from ..schemas import ModelGraph

router = APIRouter(prefix="/api/graph", tags=["graphs"])


@router.get("/demo", response_model=ModelGraph)
def get_demo_graph(name: str = "lenet-mnist") -> ModelGraph:
    """Return a hardcoded demo ModelGraph. M2 grows this into a gallery."""
    if name not in DEMOS:
        raise HTTPException(404, f"Unknown demo {name!r}. Available: {sorted(DEMOS)}")
    return DEMOS[name]


@router.get("/demos", response_model=list[str])
def list_demos() -> list[str]:
    return sorted(DEMOS)
