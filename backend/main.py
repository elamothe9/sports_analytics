from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routers import leaders

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(leaders.router, prefix="/api")

@app.get("/")
def root():
    return {"message": "Analytic Overview API is running"}