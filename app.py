import os
import gradio as gr
from backend.app.main import app

# Gradio block to satisfy Hugging Face Spaces SDK requirement
with gr.Blocks(title="LayerLens 3D") as demo:
    gr.Markdown("# ◈ LayerLens v2")
    gr.Markdown("Full interactive 3D model inspector active at root `/`.")

# Mount gradio at /gradio so root / serves our full React 3D SPA
gr.mount_gradio_app(app, demo, path="/gradio")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=7860)
