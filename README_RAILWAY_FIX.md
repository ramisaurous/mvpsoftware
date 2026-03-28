Drop these files into your repo root.

Required repo shape:
- requirements.txt at the repo root
- app/main.py containing `app = FastAPI()`

If your repo is structured like:
    gm_suv_shop_grade/
      app/
        main.py
      requirements.txt

then either:
1) put these files inside `gm_suv_shop_grade`, OR
2) set Railway Root Directory to `gm_suv_shop_grade`

Railway start target used here:
    uvicorn app.main:app --host 0.0.0.0 --port $PORT

Quick checks:
- app/main.py must define: app = FastAPI()
- no `--reload` in production
- if imports fail, add the missing packages to requirements.txt
