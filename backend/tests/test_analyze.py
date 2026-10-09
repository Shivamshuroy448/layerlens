"""M1: POST /api/analyze resolves a REAL Hugging Face architecture.

Live-network tests against huggingface.co: config.json + model metadata are
fetched, the model is instantiated on meta tensors (no weight download), and
the true module hierarchy is returned. Slower than the M0 contract tests —
that's the price of touching the real Hub.
"""
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_analyze_bert_tiny():
    r = client.post("/api/analyze", json={"model_id": "prajjwal1/bert-tiny"})
    assert r.status_code == 200, r.text[:600]
    body = r.json()

    s = body["summary"]
    assert s["n_parameters"] > 0
    assert s["hidden_size"] == 128
    assert s["num_hidden_layers"] == 2

    assert len(body["nodes"]) > 10
    assert len(body["edges"]) > 0

    ids = {n["id"] for n in body["nodes"]}
    assert any("encoder" in i for i in ids), "encoder stack missing from node ids"

    # every edge must reference real nodes
    for e in body["edges"]:
        assert e["source"] in ids and e["target"] in ids

    # tree root wraps the hierarchy
    assert len(body["tree"]) == 1
    assert body["tree"][0]["children"], "tree has no children"


def test_analyze_accepts_full_url():
    r = client.post(
        "/api/analyze",
        json={"model_id": "https://huggingface.co/prajjwal1/bert-tiny"},
    )
    assert r.status_code == 200
    assert r.json()["model_id"] == "prajjwal1/bert-tiny"


def test_analyze_unknown_model_404s():
    r = client.post(
        "/api/analyze", json={"model_id": "no-such-org-xyz-123/no-such-model-xyz-123"}
    )
    assert r.status_code == 404


def test_analyze_garbage_id_400s():
    r = client.post("/api/analyze", json={"model_id": "not a model!!"})
    assert r.status_code == 400


def test_analyze_custom_architecture_falls_back_to_config_tree():
    # Cactus-Compute/whistle is not a transformers architecture
    # (custom 'whistle' model_type, custom .cact runtime) — analysis must
    # succeed with resolved=false and a browsable config.json tree.
    r = client.post("/api/analyze", json={"model_id": "Cactus-Compute/whistle"})
    assert r.status_code == 200, r.text[:600]
    body = r.json()

    assert body["resolved"] is False
    assert body["note"], "fallback must explain itself"

    assert len(body["nodes"]) > 5
    assert len(body["tree"]) == 1
    root = body["tree"][0]
    assert root["name"] == "config"

    # leaf values survive, e.g. model_type = 'whistle'
    def leaves(n):
        if not n["children"]:
            yield n
        for c in n["children"]:
            yield from leaves(c)

    vals = {n["name"]: n["value"] for n in leaves(root)}
    assert vals.get("model_type") == "'whistle'"
    assert "engine" in vals


def test_analyze_flow_edges_trace_execution_order():
    r = client.post("/api/analyze", json={"model_id": "prajjwal1/bert-tiny"})
    assert r.status_code == 200, r.text[:600]
    body = r.json()

    flow = body["flow_edges"]
    assert len(flow) > 10, "expected a real execution trace"

    ids = {n["id"] for n in body["nodes"]}
    for e in flow:
        assert e["source"] in ids and e["target"] in ids
        assert e["source"] != e["target"], "no self loops"

    # the trace starts at the embeddings and ends at the pooler
    assert "embeddings" in flow[0]["source"]
    assert "pooler" in flow[-1]["target"]
