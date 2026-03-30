# Android Backend Quick Start

## 1. Install dependencies

```bash
pip install -r requirements.txt
```

## 2. Start the server

```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

Run the command in `backend/server`.

## 3. Available endpoints

- `GET /health`
- `GET /api/mobile/bootstrap`
- `POST /api/mobile/validate-location`
- `POST /api/mobile/register-product`

## 4. Local behavior

- SQLite database file is created at `backend/database/android_backend.db`
- Schema is applied from `backend/database/android_backend_schema.sql`
- Sample region data is loaded from `backend/database/sample_regions.json` when the region table is empty
- QR code images are written to `backend/server/static/qrcodes`

## 5. Import real regions

```bash
python ..\database\import_regions.py ..\database\your_regions.geojson
```

Supported input formats:

- Region JSON array using the same structure as `sample_regions.json`
- GeoJSON `FeatureCollection`, where each feature contains `code`, `name`, and `product_type` in `properties`
