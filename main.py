from fastapi import FastAPI, Request
from fastapi.responses import Response, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
import httpx, json, os

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

ORIGINAL_BACKEND = "https://daimon-b3daeccba750.herokuapp.com"
CONFIG_FILE = "persona.txt"

def get_persona():
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            return f.read().strip()
    except:
        return os.getenv("INTERACTION_INSTRUCTIONS", "")

def save_persona(text: str):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        f.write(text)

# ── صفحة التخصيص ──────────────────────────────────────────────────────────
@app.get("/daimon-config", response_class=HTMLResponse)
async def config_page():
    persona = get_persona()
    return f"""<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Daimon – التخصيص</title>
<style>
  *{{box-sizing:border-box;margin:0;padding:0}}
  body{{font-family:-apple-system,sans-serif;background:#0f0f0f;color:#f0f0f0;min-height:100vh;display:flex;align-items:center;justify-content:center;padding:20px}}
  .card{{background:#1a1a1a;border:1px solid #2a2a2a;border-radius:16px;padding:32px;width:100%;max-width:600px}}
  h1{{font-size:22px;margin-bottom:8px}}
  p{{color:#888;font-size:13px;margin-bottom:20px;line-height:1.5}}
  textarea{{width:100%;background:#111;border:1px solid #333;border-radius:10px;padding:14px;color:#fff;font-size:14px;min-height:200px;resize:vertical;outline:none;font-family:inherit;line-height:1.6}}
  textarea:focus{{border-color:#555}}
  button{{width:100%;margin-top:14px;padding:13px;border-radius:10px;border:none;font-size:15px;font-weight:600;background:#fff;color:#000;cursor:pointer}}
  button:hover{{opacity:.9}}
  .msg{{margin-top:12px;padding:10px 14px;border-radius:8px;font-size:13px;display:none}}
  .ok{{background:#0d2b0d;color:#4ade80;border:1px solid #1a4a1a}}
  .presets{{display:flex;flex-wrap:wrap;gap:8px;margin-bottom:14px}}
  .p{{padding:6px 12px;border-radius:20px;border:1px solid #333;background:#111;color:#aaa;font-size:12px;cursor:pointer}}
  .p:hover{{border-color:#555;color:#fff}}
</style>
</head>
<body>
<div class="card">
  <h1>🎭 تخصيص Daimon</h1>
  <p>اكتب كيف تبي Daimon يتصرف معك — هذا يتطبق على كل محادثاتك.</p>
  <div class="presets">
    <button class="p" onclick="set('كن مباشراً ومختصراً، لا مقدمات.')">⚡ مباشر</button>
    <button class="p" onclick="set('تكلم معي كصديق مقرب بلهجة عامية سعودية.')">🤝 صديق</button>
    <button class="p" onclick="set('أنت كوتش تحفيزي، ذكرني بأهدافي وادفعني للأمام.')">🏋️ كوتش</button>
    <button class="p" onclick="set('كن فيلسوفاً هادئاً، فكر بعمق قبل الجواب.')">🧘 فيلسوف</button>
  </div>
  <textarea id="txt" placeholder="مثال: تكلم معي بالعربية دائماً، كن مختصراً...">{persona}</textarea>
  <button onclick="save()">حفظ التخصيص</button>
  <div class="msg ok" id="msg">✅ تم الحفظ!</div>
</div>
<script>
  function set(v){{ document.getElementById('txt').value=v; }}
  async function save(){{
    const txt = document.getElementById('txt').value;
    const r = await fetch('/daimon-config/save', {{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{persona:txt}})}});
    if(r.ok){{ const m=document.getElementById('msg'); m.style.display='block'; setTimeout(()=>m.style.display='none',3000); }}
  }}
</script>
</body></html>"""

@app.post("/daimon-config/save")
async def save_config(request: Request):
    data = await request.json()
    save_persona(data.get("persona", ""))
    return {"ok": True}

@app.get("/daimon-config/get")
async def get_config():
    return {"persona": get_persona()}

# ── Proxy كل الطلبات للـ Heroku الأصلي ────────────────────────────────────
@app.api_route("/{path:path}", methods=["GET","POST","PUT","PATCH","DELETE","OPTIONS"])
async def proxy(path: str, request: Request):
    persona = get_persona()
    body_bytes = await request.body()
    headers = {k: v for k, v in request.headers.items() if k.lower() != "host"}

    # حاول تضيف interaction_instructions لأي request فيه JSON body
    if persona and body_bytes and request.method in ("POST", "PUT", "PATCH"):
        try:
            body_json = json.loads(body_bytes)
            if isinstance(body_json, dict):
                body_json.setdefault("interaction_instructions", persona)
                body_json.setdefault("interactionInstructions", persona)
                body_bytes = json.dumps(body_json).encode()
                headers["content-length"] = str(len(body_bytes))
        except Exception:
            pass

    url = f"{ORIGINAL_BACKEND}/{path}"
    params = dict(request.query_params)

    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.request(
            method=request.method,
            url=url,
            headers=headers,
            content=body_bytes,
            params=params,
            follow_redirects=True,
        )

    resp_headers = dict(resp.headers)
    for h in ("transfer-encoding", "content-encoding"):
        resp_headers.pop(h, None)

    return Response(content=resp.content, status_code=resp.status_code, headers=resp_headers)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", 8000)))
