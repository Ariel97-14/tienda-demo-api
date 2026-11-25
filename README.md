# Tienda Demo API

API de inventario y ventas para una **tienda ficticia**. Es un proyecto independiente de portfolio: no usa datos, código ni credenciales de clientes. Permite registrar productos, crear pedidos sin vender más unidades que las disponibles y consultar un resumen de ventas.

## Qué demuestra

- API HTTP con FastAPI y documentación OpenAPI en `/docs`.
- Persistencia SQLite con consultas parametrizadas y claves foráneas.
- Pedido atómico: si un producto no existe o falta stock, no se registra ningún cambio.
- Precios guardados como enteros en centavos y precio unitario conservado en cada línea de pedido.
- Validación de entradas y pruebas de integración con una base temporal por prueba.

## Requisitos e instalación

Python 3.11 o superior. Desde esta carpeta:

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -e ".[test]"
.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

En Linux o macOS, usá `.venv/bin/python` en lugar de `.venv\Scripts\python.exe`. Abrí `http://127.0.0.1:8000/docs` para probar los endpoints. La base `tienda.sqlite3` se crea al iniciar el servidor y está excluida de Git.

## Ejemplo rápido

En `/docs`, ejecutá `POST /products`:

```json
{"sku":"CUAD-01","name":"Cuaderno","price_cents":2500,"stock":10}
```

Con el `id` devuelto, ejecutá `POST /orders`:

```json
{"items":[{"product_id":1,"quantity":3}]}
```

Después consultá `GET /products`, `GET /orders` y `GET /reports/summary` para ver el stock, el pedido y el total. El ejemplo usa productos inventados.

## Pruebas

```powershell
.venv\Scripts\python.exe -m pytest -q
```

## Alcance

Esta API es una demostración local para portfolio. No incluye autenticación, control de permisos, migraciones ni despliegue de producción. Antes de exponer una API de ventas real habría que incorporar esas piezas y revisar seguridad, observabilidad y respaldos.

