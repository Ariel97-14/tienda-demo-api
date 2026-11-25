from fastapi.testclient import TestClient

from app.main import create_app


def client_for(tmp_path):
    return TestClient(create_app(tmp_path / "test.sqlite3"))


def test_product_and_order_flow(tmp_path):
    with client_for(tmp_path) as client:
        created = client.post("/products", json={"sku": "CUAD-01", "name": "Cuaderno", "price_cents": 2500, "stock": 10})
        assert created.status_code == 201
        product = created.json()
        assert product["stock"] == 10

        order = client.post("/orders", json={"items": [{"product_id": product["id"], "quantity": 3}]})
        assert order.status_code == 201
        assert order.json()["total_cents"] == 7500
        assert order.json()["items"][0]["unit_price_cents"] == 2500
        assert client.get("/products").json()[0]["stock"] == 7
        assert client.get("/reports/summary").json() == {"orders": 1, "units_sold": 3, "revenue_cents": 7500}


def test_insufficient_stock_does_not_create_partial_order(tmp_path):
    with client_for(tmp_path) as client:
        first = client.post("/products", json={"sku": "LAP-01", "name": "Lápiz", "price_cents": 500, "stock": 2}).json()
        second = client.post("/products", json={"sku": "BOL-01", "name": "Bolígrafo", "price_cents": 900, "stock": 1}).json()
        response = client.post("/orders", json={"items": [
            {"product_id": first["id"], "quantity": 1},
            {"product_id": second["id"], "quantity": 2},
        ]})
        assert response.status_code == 409
        assert client.get("/products").json()[0]["stock"] == 2
        assert client.get("/orders").json() == []


def test_duplicate_sku_is_rejected(tmp_path):
    with client_for(tmp_path) as client:
        payload = {"sku": "RES-01", "name": "Resaltador", "price_cents": 1200, "stock": 4}
        assert client.post("/products", json=payload).status_code == 201
        assert client.post("/products", json=payload).status_code == 409


def test_invalid_data_and_duplicate_order_line_are_rejected(tmp_path):
    with client_for(tmp_path) as client:
        assert client.post("/products", json={"sku": "X", "name": "", "price_cents": -1, "stock": -2}).status_code == 422
        product = client.post("/products", json={"sku": "CAR-01", "name": "Carpeta", "price_cents": 3000, "stock": 5}).json()
        duplicate = {"items": [{"product_id": product["id"], "quantity": 1}, {"product_id": product["id"], "quantity": 1}]}
        assert client.post("/orders", json=duplicate).status_code == 422
        assert client.get("/reports/summary").json()["orders"] == 0

