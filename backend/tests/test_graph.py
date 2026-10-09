"""M0 contract tests: the demo graph must be a valid ModelGraph
whose edges reference real nodes — this is the handshake the
3D frontend relies on."""
from fastapi.testclient import TestClient

from app.demo_graphs import DEMOS
from app.main import app
from app.schemas import ModelGraph

client = TestClient(app)


def test_demo_graph_is_valid_model_graph():
    for name, graph in DEMOS.items():
        assert isinstance(graph, ModelGraph), name
        ids = graph.node_ids()
        for e in graph.edges:
            assert e.source in ids, f"{name}: edge from unknown {e.source}"
            assert e.target in ids, f"{name}: edge to unknown {e.target}"


def test_get_demo_endpoint():
    r = client.get("/api/graph/demo")
    assert r.status_code == 200
    graph = ModelGraph.model_validate(r.json())
    assert len(graph.nodes) > 0
    assert graph.nodes[0].id == "input"
    assert graph.nodes[-1].id == "output"


def test_unknown_demo_404s():
    assert client.get("/api/graph/demo?name=nope").status_code == 404


def test_health():
    assert client.get("/api/health").json()["status"] == "ok"
