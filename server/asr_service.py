# -*- coding: utf-8 -*-
# ASR service for RK3588 solder UI voice button. SenseVoice-Small int8 (sherpa-onnx).
import io, wave, time, os
import numpy as np
import sherpa_onnx
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
import uvicorn

MODEL_DIR = os.environ.get("EDISPENSE_ASR_MODEL_DIR", r"models/sensevoice")
MODEL_NAME = "sensevoice-small-int8"
print("loading sensevoice model...", flush=True)
_t = time.time()
REC = sherpa_onnx.OfflineRecognizer.from_sense_voice(
    model=os.path.join(MODEL_DIR, "model.int8.onnx"),
    tokens=os.path.join(MODEL_DIR, "tokens.txt"),
    use_itn=True,
    num_threads=2,
    language="auto",
)
print("model loaded in %.1fs" % (time.time() - _t), flush=True)

app = FastAPI()

def wav_bytes_to_16k_mono(data: bytes):
    """Parse WAV bytes, mix to mono, resample to 16k float32 [-1,1]."""
    wf = wave.open(io.BytesIO(data), "rb")
    ch = wf.getnchannels()
    sr = wf.getframerate()
    sw = wf.getsampwidth()
    n = wf.getnframes()
    raw = wf.readframes(n)
    wf.close()
    if sw != 2:
        raise ValueError("only 16-bit PCM supported, got sampwidth=%d" % sw)
    arr = np.frombuffer(raw, dtype=np.int16).astype(np.float32)
    if ch > 1:
        arr = arr.reshape(-1, ch).mean(axis=1)
    arr = arr / 32768.0
    if sr != 16000:
        new_len = int(round(len(arr) * 16000.0 / sr))
        if new_len < 1:
            new_len = 1
        x_old = np.linspace(0, 1, num=len(arr), endpoint=False)
        x_new = np.linspace(0, 1, num=new_len, endpoint=False)
        arr = np.interp(x_new, x_old, arr).astype(np.float32)
    return arr

@app.get("/health")
def health():
    return {"ok": True, "model": MODEL_NAME, "lang": "auto"}

@app.post("/asr")
async def asr(request: Request):
    try:
        data = await request.body()
        if not data or len(data) < 100:
            return JSONResponse({"ok": False, "error": "empty audio"}, status_code=400)
        t0 = time.time()
        audio = wav_bytes_to_16k_mono(data)
        dur = len(audio) / 16000.0
        rms = float(np.sqrt(np.mean(audio ** 2))) if len(audio) else 0.0
        s = REC.create_stream()
        s.accept_waveform(16000, audio)
        REC.decode_stream(s)
        text = s.result.text.strip()
        dt = time.time() - t0
        print("[ASR] %.2fs dur=%.2fs rms=%.4f -> %r" % (dt, dur, rms, text), flush=True)
        return {"ok": True, "text": text, "dur": round(dur, 2), "cost": round(dt, 2), "rms": round(rms, 4)}
    except Exception as e:
        import traceback; traceback.print_exc()
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8010, log_level="warning")
