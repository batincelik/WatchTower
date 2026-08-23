from datetime import datetime

from fastapi import FastAPI
from fastapi.responses import HTMLResponse

app = FastAPI()
changed = False


@app.get("/", response_class=HTMLResponse)
async def product() -> str:
    price, availability = ("$80", "Out of Stock") if changed else ("$100", "In Stock")
    return f"""<!doctype html><html><body><main data-testid="product">
    <h1>Demo Product</h1><p class="price">{price}</p>
    <p id="availability">{availability}</p>
    <time class="dynamic-timestamp">{datetime.now().strftime("%H:%M:%S")}</time>
    </main></body></html>"""


@app.post("/change")
async def change() -> dict[str, bool]:
    global changed
    changed = not changed
    return {"changed": changed}
