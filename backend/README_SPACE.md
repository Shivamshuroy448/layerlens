---
title: LayerLens Backend
emoji: ◈
colorFrom: indigo
colorTo: purple
sdk: docker
app_port: 7860
pinned: false
---

# LayerLens Backend (PyTorch + Transformers Meta Tensors)

FastAPI service for LayerLens. Resolves neural network architectures on empty meta tensors and runs FakeTensorMode data-flow tracing.

### Deploying to Hugging Face Spaces:
1. Create a new Space on [huggingface.co/new-space](https://huggingface.co/new-space).
2. Choose **Docker** as the Space SDK (Blank template).
3. Copy the files in `backend/` (`Dockerfile`, `requirements.txt`, `app/`, `README.md`) to the Space repository.
4. Hugging Face builds and runs the container with 16GB RAM for free.
