import subprocess
import sys
from pathlib import Path

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

import store

app = FastAPI(title="StocksInfo Dashboard")
templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))


@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request, msg: str = ""):
    watchlist = store.load_watchlist()
    report_config = store.load_report_config()
    symbols = watchlist.get("symbols", [])
    return templates.TemplateResponse(request, "index.html", {
        "us_stocks": [e["symbol"] for e in symbols if e.get("market") == "us"],
        "kr_stocks": [e["symbol"] for e in symbols if e.get("market") == "kr"],
        "emails": report_config.get("email", {}).get("recipients", []),
        "msg": msg,
    })


@app.post("/watchlist/add")
async def add_stock(market: str = Form(...), symbol: str = Form(...)):
    symbol = symbol.strip().upper()
    if not symbol:
        return RedirectResponse("/?msg=심볼을+입력하세요", status_code=303)
    wl = store.load_watchlist()
    symbols = wl.setdefault("symbols", [])
    if symbol not in {e["symbol"] for e in symbols}:
        symbols.append({"symbol": symbol, "name": "", "market": market, "profile": "watching", "memo": ""})
        store.save_watchlist(wl)
    return RedirectResponse(f"/?msg={symbol}+추가됨", status_code=303)


@app.post("/watchlist/delete")
async def delete_stock(market: str = Form(...), symbol: str = Form(...)):
    wl = store.load_watchlist()
    wl["symbols"] = [e for e in wl.get("symbols", []) if e["symbol"] != symbol]
    store.save_watchlist(wl)
    return RedirectResponse(f"/?msg={symbol}+삭제됨", status_code=303)


@app.post("/recipients/add")
async def add_recipient(email: str = Form(...)):
    email = email.strip()
    if not email:
        return RedirectResponse("/?msg=이메일을+입력하세요", status_code=303)
    cfg = store.load_report_config()
    recipients = cfg.setdefault("email", {}).setdefault("recipients", [])
    if email not in recipients:
        recipients.append(email)
        store.save_report_config(cfg)
    return RedirectResponse(f"/?msg={email}+추가됨", status_code=303)


@app.post("/recipients/delete")
async def delete_recipient(email: str = Form(...)):
    cfg = store.load_report_config()
    cfg.setdefault("email", {})["recipients"] = [
        e for e in cfg.get("email", {}).get("recipients", []) if e != email
    ]
    store.save_report_config(cfg)
    return RedirectResponse("/?msg=이메일+삭제됨", status_code=303)


@app.post("/push")
async def push_to_github():
    try:
        subprocess.run(["git", "add", "config/watchlist.json", "config/report.json"], cwd=ROOT, check=True)
        subprocess.run(["git", "commit", "-m", "Update watchlist/recipients via dashboard"], cwd=ROOT, check=True)
        subprocess.run(["git", "push"], cwd=ROOT, check=True)
        return RedirectResponse("/?msg=GitHub+push+완료", status_code=303)
    except subprocess.CalledProcessError as e:
        return RedirectResponse(f"/?msg=push+실패:+{e}", status_code=303)


@app.post("/run-now")
async def run_now():
    try:
        result = subprocess.run(
            [sys.executable, str(ROOT / "main.py")],
            cwd=ROOT, capture_output=True, text=True, timeout=120
        )
        msg = "리포트+전송+완료" if result.returncode == 0 else f"오류:{result.stderr[-100:]}"
        return RedirectResponse(f"/?msg={msg}", status_code=303)
    except Exception as e:
        return RedirectResponse(f"/?msg=실행+실패:{e}", status_code=303)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("web.app:app", host="0.0.0.0", port=8000, reload=True, app_dir=str(ROOT))
