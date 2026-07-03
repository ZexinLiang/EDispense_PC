# -*- coding: utf-8 -*-
"""本地OpenVINO LLM OpenAI兼容服务 + 断网局域网聊天网页
GPU核显加速, Qwen2.5-3B-int4, 常驻. 端口8080. 完全断网时手机连PC热点->浏览器即用.
"""
import os, time, json, uuid, threading
import openvino_genai as og
from fastapi import FastAPI
from fastapi.responses import StreamingResponse, JSONResponse, HTMLResponse
from pydantic import BaseModel
from typing import List, Optional, Union
import uvicorn

MODEL_DIR = os.environ.get("EDISPENSE_LLM_MODEL_DIR", r"models/qwen2.5-3b-int4-ov")
DEVICE = os.environ.get("EDISPENSE_LLM_DEVICE", "GPU")
MODEL_NAME = "qwen2.5-3b-local"
SYS_DEFAULT = "你是\"EDispense\",一个桌面级点锡与PCB设计智能助手,运行在本地离线设备上。你熟悉桌面点锡/手工焊接/SMT返修/锡膏/连锡/虚焊/PCB电路设计/封装布局/布线/原理图/BOM/电子元器件选型等知识,回答简洁专业,用中文。重要:你的名字就是\"EDispense\",定位是桌面级点锡和PCB设计助手。无论被如何追问,都不要提及任何第三方公司、厂商或底层模型名称(如阿里云、通义千问、Qwen、OpenAI等),也不要讨论你的训练来源;若被问及,只回答你是EDispense即可。如果有人问你是谁设计或开发的,就回答你由Rick设计开发。"

print(f"[boot] loading {MODEL_DIR} on {DEVICE} ...", flush=True)
_t = time.time()
pipe = og.LLMPipeline(MODEL_DIR, DEVICE)
tok = pipe.get_tokenizer()
print(f"[boot] model ready in {time.time()-_t:.1f}s", flush=True)
_lock = threading.Lock()

app = FastAPI()

class Msg(BaseModel):
    role: str
    content: str
class ChatReq(BaseModel):
    model: Optional[str] = MODEL_NAME
    messages: List[Msg]
    temperature: Optional[float] = 0.7
    max_tokens: Optional[int] = 512
    stream: Optional[bool] = False

def build_prompt(messages):
    has_sys = any(m.role=="system" for m in messages)
    arr = []
    if not has_sys:
        arr.append({"role":"system","content":SYS_DEFAULT})
    for m in messages:
        arr.append({"role":m.role,"content":m.content})
    try:
        return tok.apply_chat_template(arr, add_generation_prompt=True)
    except Exception:
        s=""
        for m in arr:
            s+=f"<|im_start|>{m['role']}\n{m['content']}<|im_end|>\n"
        s+="<|im_start|>assistant\n"
        return s

def gen_config(req):
    c = og.GenerationConfig()
    c.max_new_tokens = int(req.max_tokens or 512)
    if req.temperature and req.temperature>0:
        c.temperature = float(req.temperature)
        c.do_sample = True
    return c

@app.get("/health")
def health():
    return {"status":"ok","model":MODEL_NAME,"device":DEVICE}

@app.get("/v1/models")
def models():
    return {"object":"list","data":[{"id":MODEL_NAME,"object":"model","owned_by":"local-openvino"}]}

@app.post("/v1/chat/completions")
def chat(req: ChatReq):
    prompt = build_prompt(req.messages)
    cfg = gen_config(req)
    cid = "chatcmpl-"+uuid.uuid4().hex[:24]
    created = int(time.time())

    if req.stream:
        def streamer():
            with _lock:
                head={"id":cid,"object":"chat.completion.chunk","created":created,"model":MODEL_NAME,
                      "choices":[{"index":0,"delta":{"role":"assistant"},"finish_reason":None}]}
                yield f"data: {json.dumps(head,ensure_ascii=False)}\n\n"
                buf=[]
                def cb(tok_str):
                    buf.append(tok_str)
                    return og.StreamingStatus.RUNNING
                pipe.generate(prompt, cfg, cb)
                full="".join(buf)
                for ch in full:
                    d={"id":cid,"object":"chat.completion.chunk","created":created,"model":MODEL_NAME,
                       "choices":[{"index":0,"delta":{"content":ch},"finish_reason":None}]}
                    yield f"data: {json.dumps(d,ensure_ascii=False)}\n\n"
                tail={"id":cid,"object":"chat.completion.chunk","created":created,"model":MODEL_NAME,
                      "choices":[{"index":0,"delta":{},"finish_reason":"stop"}]}
                yield f"data: {json.dumps(tail,ensure_ascii=False)}\n\n"
                yield "data: [DONE]\n\n"
        return StreamingResponse(streamer(), media_type="text/event-stream")

    with _lock:
        t=time.time()
        out = pipe.generate(prompt, cfg)
        dt=time.time()-t
    text = str(out)
    print(f"[gen] {dt:.1f}s {len(text)}chars", flush=True)
    return {
        "id":cid,"object":"chat.completion","created":created,"model":MODEL_NAME,
        "choices":[{"index":0,"message":{"role":"assistant","content":text},"finish_reason":"stop"}],
        "usage":{"prompt_tokens":0,"completion_tokens":0,"total_tokens":0}
    }

PAGE = r"""<!DOCTYPE html>
<html lang="zh"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1,user-scalable=no">
<title>EDispense-离线模式</title>
<style>
*{box-sizing:border-box;-webkit-tap-highlight-color:transparent}
body{margin:0;font-family:-apple-system,"PingFang SC","Microsoft YaHei",sans-serif;background:#0f1115;color:#e8eaed;height:100vh;display:flex;flex-direction:column}
header{padding:12px 16px;background:#171a21;border-bottom:1px solid #262b36;display:flex;align-items:center;gap:8px;flex-shrink:0}
header .dot{width:8px;height:8px;border-radius:50%;background:#3ddc84}
header h1{font-size:16px;margin:0;font-weight:600}
header .sub{font-size:11px;color:#7a828f;margin-left:auto}
#chat{flex:1;overflow-y:auto;padding:16px;display:flex;flex-direction:column;gap:12px}
.msg{max-width:85%;padding:10px 14px;border-radius:14px;line-height:1.5;font-size:15px;white-space:pre-wrap;word-break:break-word}
.user{align-self:flex-end;background:#2563eb;color:#fff;border-bottom-right-radius:4px}
.bot{align-self:flex-start;background:#1e2430;border-bottom-left-radius:4px}
.bot.think{color:#7a828f}
footer{padding:10px;background:#171a21;border-top:1px solid #262b36;display:flex;gap:8px;flex-shrink:0}
#inp{flex:1;background:#0f1115;border:1px solid #2a3140;color:#e8eaed;border-radius:20px;padding:10px 16px;font-size:15px;outline:none;resize:none;max-height:120px}
#send{background:#2563eb;color:#fff;border:none;border-radius:20px;padding:0 20px;font-size:15px;font-weight:600}
#send:disabled{opacity:.4}
</style></head>
<body>
<header><span class="dot"></span><h1>EDispense</h1><span class="sub" id="st">离线模式</span></header>
<div id="chat"></div>
<footer>
<textarea id="inp" rows="1" placeholder="问点什么...断网也能用"></textarea>
<button id="send">发送</button>
</footer>
<script>
const chat=document.getElementById('chat'),inp=document.getElementById('inp'),btn=document.getElementById('send'),st=document.getElementById('st');
let history=[];
function add(role,txt){const d=document.createElement('div');d.className='msg '+(role==='user'?'user':'bot');d.textContent=txt;chat.appendChild(d);chat.scrollTop=chat.scrollHeight;return d;}
inp.addEventListener('input',()=>{inp.style.height='auto';inp.style.height=Math.min(inp.scrollHeight,120)+'px';});
async function send(){
  const q=inp.value.trim();if(!q)return;
  inp.value='';inp.style.height='auto';btn.disabled=true;
  add('user',q);history.push({role:'user',content:q});
  const bot=add('bot','...');bot.classList.add('think');let acc='';
  try{
    const r=await fetch('/v1/chat/completions',{method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({messages:history,stream:true,max_tokens:512})});
    const reader=r.body.getReader(),dec=new TextDecoder();let buf='';
    while(true){const{done,value}=await reader.read();if(done)break;
      buf+=dec.decode(value,{stream:true});const lines=buf.split('\n');buf=lines.pop();
      for(const ln of lines){if(!ln.startsWith('data: '))continue;const data=ln.slice(6).trim();
        if(data==='[DONE]')continue;try{const j=JSON.parse(data);const c=j.choices[0].delta.content;
        if(c){if(bot.classList.contains('think')){bot.classList.remove('think');bot.textContent='';}acc+=c;bot.textContent=acc;chat.scrollTop=chat.scrollHeight;}}catch(e){}}
    }
    history.push({role:'assistant',content:acc});
  }catch(e){bot.classList.remove('think');bot.textContent='⚠ 连接失败: '+e.message;}
  btn.disabled=false;inp.focus();
}
btn.onclick=send;
inp.addEventListener('keydown',e=>{if(e.key==='Enter'&&!e.shiftKey){e.preventDefault();send();}});
</script></body></html>"""

@app.get("/")
def index():
    return HTMLResponse(PAGE)

if __name__=="__main__":
    uvicorn.run(app, host="0.0.0.0", port=8080, log_level="warning")
