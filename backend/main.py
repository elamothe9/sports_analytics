from fastapi import FastAPI

app = FastAPI()

@app.get("/")
def root():
    return {"message": "sports_analytics API is running"}