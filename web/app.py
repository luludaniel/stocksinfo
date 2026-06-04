import subprocess
import sys
from pathlib import Path

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from store import load_watchlist, save_watchlist, load_recipients, save_recipients

app = FastAPI(title="StocksInfo Dashboard")
templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))


@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request, msg: str = ""):
    watchlist = load_watchlist()
    recipients = load_recipients()
    return templates.TemplateResponse("index.html", {
        "request": request,
        "us_stocks": watchlist.get("us", []),
        "kr_stocks": watchlist.get("kr", []),
        "emails": recipients.get("emails", []),
        "msg": msg,
    })


@app.post("/watchlist/add")
async def add_stock(market: str = Form(...), symbol: str = Form(...)):
    symbol = symbol.strip().upper()
    if not symbol:
        return RedirectResponse("/?msg=심볼을+입력하세요", status_code=303)
    wl = load_watchlist()
    if symbol not in wl.get(market, []):
        wl.setdefault(market, []).append(symbol)
        save_watchlist(wl)
    return RedirectResponse(f"/?msg={symbol}+추가됨", status_code=303)


@app.post("/watchlist/delete")
async def delete_stock(market: str = Form(...), symbol: str = Form(...)):
    wl = load_watchlist()
    wl[market] = [s for s in wl.get(market, []) if s != symbol]
    save_watchlist(wl)
    return RedirectResponse(f"/?msg={symbol}+삭제됨", status_code=303)


@app.post("/recipients/add")
async def add_recipient(email: str = Form(...)):
    email = email.strip()
    if not email:
        return RedirectResponse("/?msg=이메일을+입력하세요", status_code=303)
    r = load_recipients()
    if email not in r.get("emails", []):
        r.setdefault("emails", []).append(email)
        save_recipients(r)
    return RedirectResponse(f"/?msg={email}+추가됨", status_code=303)


@app.post("/recipients/delete")
async def delete_recipient(email: str = Form(...)):
    r = load_recipients()
    r["emails"] = [e for e in r.get("emails", []) if e != email]
    save_recipients(r)
    return RedirectResponse("/?msg=이메일+삭제됨", status_code=303)


@app.post("/push")
async def push_to_github():
    try:
        subprocess.run(["git", "add", "watchlist.json", "recipients.json"], cwd=ROOT, check=True)
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
