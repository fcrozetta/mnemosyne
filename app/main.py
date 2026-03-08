from fastapi import FastAPI

from app.router.notes import router as notes_router

app = FastAPI(title="Mnemosyne API", version="0.1.0")
app.include_router(notes_router)
