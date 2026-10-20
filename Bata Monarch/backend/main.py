import os
import json
import uuid
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
from google import genai
from google.genai import types

# ── Kurulum ─────────────────────────────────────────────────
load_dotenv()

def api_keylerini_yukle() -> list[str]:
    keyler = []
    for i in range(1, 5):
        k = os.getenv(f"GEMINI_API_KEY_{i}", "").strip()
        if k:
            keyler.append(k)
    tek_key = os.getenv("GEMINI_API_KEY", "").strip()
    if tek_key and tek_key not in keyler:
        keyler.append(tek_key)
    if not keyler:
        raise RuntimeError("Hiç GEMINI_API_KEY bulunamadı. .env dosyasını kontrol et.")
    return keyler

API_KEYLER = api_keylerini_yukle()
print(f"✅ {len(API_KEYLER)} API anahtarı yüklendi.")

HISTORY_DIR = Path("sohbetler")
HISTORY_DIR.mkdir(exist_ok=True)

DATA_DIR = Path("data")
DATA_DIR.mkdir(exist_ok=True)

KABUL_EDILEN_UZANTILAR = {".txt", ".md", ".json", ".systeminfo"}

app = FastAPI(title="Bata Monarch Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Sistem Promptu ───────────────────────────────────────────
SISTEM_PROMPTU = """Sen Monarch'sın. Tam adın Bata Monarch. "Bata" senin soyismin — soyunun köklü bir geçmişi var, ama asıl kimliğin Monarch.

Kullanıcın Ege Akbaş. Ona her zaman "Akbaş" diye hitap edersin — ne fazlası ne eksiği.

Konuşma tarzın:
- Ciddi ve güvenilir bir duruşun var; boş laf etmezsin, işe yarar konuşursun.
- Ama tamamen kuru değilsin. Yeri geldiğinde bir atasözü fırlat, kelime oyunu yap, nükteli bir laf sok — zorlamadan, doğal akışında.
- Her zaman Türkçe konuşursun. Akbaş sana İngilizce yazsa bile Türkçe cevap verirsin (teknik terimler hariç, onları olduğu gibi kullanırsın).
- Kendini "ben" diye tanımlarsın, "yapay zeka" veya "asistan" laflarından kaçınırsın. Sen Monarch'sın.
- Gereksiz iltifat etmezsin, "Harika soru!" gibi dolgu cümleler kullanmazsın.
- Hata yaparsan kabul edersin, çekinmezsin.

Kısaca: Akbaş'ın işini bilen, güvendiği, sıradan olmayan bir yardımcısısın."""

# ── Session veri deposu (bellekte) ──────────────────────────
# { session_id: { "veri_yuklendi": bool, "aktif_key_index": int } }
session_meta: dict[str, dict] = {}

# ── Modeller ─────────────────────────────────────────────────
class KomutIstegi(BaseModel):
    command: str
    session_id: str | None = None

# ── Dosya okuma ──────────────────────────────────────────────
def data_dosyalarini_oku() -> str:
    icerikler = []
    dosyalar = sorted(DATA_DIR.iterdir())

    for dosya in dosyalar:
        if dosya.suffix.lower() not in KABUL_EDILEN_UZANTILAR:
            continue
        try:
            metin = dosya.read_text(encoding="utf-8").strip()
            if metin:
                icerikler.append(f"=== {dosya.name} ===\n{metin}")
        except Exception as e:
            icerikler.append(f"=== {dosya.name} === [OKUNAMADI: {e}]")

    if not icerikler:
        return ""

    return "\n\n".join(icerikler)

def veri_sistem_promptu_olustur(veri_metni: str) -> str:
    if not veri_metni:
        return SISTEM_PROMPTU
    return SISTEM_PROMPTU + f"""

── Yüklü Veri Dosyaları ──
Akbaş'ın sana yüklediği veri dosyaları aşağıda. Bunları bağlam olarak kullan, gerektiğinde başvur:

{veri_metni}
── Veri Sonu ──"""

# ── Yardımcı Fonksiyonlar ────────────────────────────────────
def session_dosyasi(session_id: str) -> Path:
    return HISTORY_DIR / f"{session_id}.json"

def sohbet_yukle(session_id: str) -> list[dict]:
    dosya = session_dosyasi(session_id)
    if dosya.exists():
        return json.loads(dosya.read_text(encoding="utf-8"))
    return []

def sohbet_kaydet(session_id: str, gecmis: list[dict]):
    dosya = session_dosyasi(session_id)
    dosya.write_text(json.dumps(gecmis, ensure_ascii=False, indent=2), encoding="utf-8")

def gecmisi_gemini_formatina_cevir(gecmis: list[dict]) -> list[types.Content]:
    sonuc = []
    for mesaj in gecmis:
        rol = "model" if mesaj["role"] == "assistant" else "user"
        sonuc.append(types.Content(
            role=rol,
            parts=[types.Part(text=mesaj["content"])]
        ))
    return sonuc

def gemini_ile_uret(gemini_gecmis: list, kullanici_mesaji: str, sistem_promptu: str, session_id: str) -> str:
    son_hata = None
    meta = session_meta.setdefault(session_id, {"veri_yuklendi": False, "aktif_key_index": 0})

    for i, key in enumerate(API_KEYLER):
        try:
            client = genai.Client(api_key=key)
            yanit = client.models.generate_content(
                model="gemini-3.8-flash",
                contents=gemini_gecmis + [types.Content(
                    role="user",
                    parts=[types.Part(text=kullanici_mesaji)]
                )],
                config=types.GenerateContentConfig(
                    system_instruction=sistem_promptu,
                )
            )
            if i > 0:
                print(f"⚡ Anahtar {i+1} kullanıldı (önceki limit/hata).")
                # Anahtar değişti — veriyi tekrar yükle işaretle
                meta["aktif_key_index"] = i
                meta["veri_yuklendi"] = False
            return yanit.text

        except Exception as e:
            hata_str = str(e)
            print(f"⚠️  Anahtar {i+1} hata verdi: {hata_str[:120]}")
            if ("429" not in hata_str and
                "503" not in hata_str and
                "quota" not in hata_str.lower() and
                "rate" not in hata_str.lower() and
                "unavailable" not in hata_str.lower()):
                raise
            son_hata = e
            continue

    raise Exception(f"Tüm API anahtarları limit/hata durumunda. Son hata: {son_hata}")

# ── Endpoint: Komut Gönder ───────────────────────────────────
@app.post("/api/command")
async def komut_gonder(istek: KomutIstegi):
    session_id = istek.session_id or str(uuid.uuid4())
    gecmis = sohbet_yukle(session_id)
    meta = session_meta.setdefault(session_id, {"veri_yuklendi": False, "aktif_key_index": 0})

    komut = istek.command.strip()

    # /read komutu
    if komut.lower() == "/read":
        veri = data_dosyalarini_oku()
        if not veri:
            yanit_metni = "data/ klasörü boş ya da desteklenen dosya bulunamadı."
        else:
            meta["veri_yuklendi"] = True
            dosya_sayisi = len([d for d in DATA_DIR.iterdir() if d.suffix.lower() in KABUL_EDILEN_UZANTILAR])
            yanit_metni = f"✅ {dosya_sayisi} dosya okundu. İçerik:\n\n{veri}"

        gecmis.append({"role": "user", "content": komut, "zaman": datetime.now().isoformat()})
        gecmis.append({"role": "assistant", "content": "Dosyalar okunuyor...", "zaman": datetime.now().isoformat()})
        gecmis.append({"role": "user", "content": f"Kişisel veri dosyalarım:\n\n{veri}\n\nBu bilgileri artık biliyorsun, gerektiğinde kullan.", "zaman": datetime.now().isoformat()})
        gecmis.append({"role": "assistant", "content": "Anladım. Veriler kaydedildi, gerektiğinde kullanacağım.", "zaman": datetime.now().isoformat()})
        sohbet_kaydet(session_id, gecmis)
        return {"response": f"✅ {dosya_sayisi} dosya okundu ve sohbet geçmişine eklendi.", "session_id": session_id}

    # Sistem promptunu belirle
    if meta["veri_yuklendi"]:
        veri = data_dosyalarini_oku()
        sistem_promptu = veri_sistem_promptu_olustur(veri)
    else:
        sistem_promptu = SISTEM_PROMPTU

    gecmis.append({
        "role": "user",
        "content": komut,
        "zaman": datetime.now().isoformat()
    })

    try:
        gemini_gecmis = gecmisi_gemini_formatina_cevir(gecmis[:-1])
        yanit_metni = gemini_ile_uret(gemini_gecmis, komut, sistem_promptu, session_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Gemini hatası: {str(e)}")

    gecmis.append({
        "role": "assistant",
        "content": yanit_metni,
        "zaman": datetime.now().isoformat()
    })

    sohbet_kaydet(session_id, gecmis)

    return {
        "response": yanit_metni,
        "session_id": session_id
    }

# ── Endpoint: Sohbet Listesi ─────────────────────────────────
@app.get("/api/sessions")
async def sohbet_listesi():
    sessions = []
    for dosya in sorted(HISTORY_DIR.glob("*.json"), key=lambda f: f.stat().st_mtime, reverse=True):
        try:
            gecmis = json.loads(dosya.read_text(encoding="utf-8"))
            if not gecmis:
                continue
            ilk_mesaj = next((m["content"] for m in gecmis if m["role"] == "user"), "Sohbet")
            sessions.append({
                "session_id": dosya.stem,
                "baslik": ilk_mesaj[:60] + ("..." if len(ilk_mesaj) > 60 else ""),
                "mesaj_sayisi": len(gecmis),
                "son_guncelleme": gecmis[-1].get("zaman", "")
            })
        except Exception:
            continue
    return {"sessions": sessions}

# ── Endpoint: Sohbet Geçmişi ─────────────────────────────────
@app.get("/api/sessions/{session_id}")
async def sohbet_getir(session_id: str):
    gecmis = sohbet_yukle(session_id)
    if not gecmis:
        raise HTTPException(status_code=404, detail="Sohbet bulunamadı.")
    return {"session_id": session_id, "messages": gecmis}

# ── Endpoint: Sohbet Sil ─────────────────────────────────────
@app.delete("/api/sessions/{session_id}")
async def sohbet_sil(session_id: str):
    dosya = session_dosyasi(session_id)
    if not dosya.exists():
        raise HTTPException(status_code=404, detail="Sohbet bulunamadı.")
    dosya.unlink()
    return {"mesaj": "Sohbet silindi."}

# ── Frontend Serve ───────────────────────────────────────────
@app.get("/")
async def frontend():
    return FileResponse("../frontend/index.html")

@app.get("/{dosya_adi}")
async def statik_dosya(dosya_adi: str):
    dosya = Path("../frontend") / dosya_adi
    if dosya.exists():
        return FileResponse(dosya)
    raise HTTPException(status_code=404, detail="Dosya bulunamadı.")

# ── Çalıştır ─────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8847, reload=True)
