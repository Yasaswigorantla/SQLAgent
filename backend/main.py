from fastapi import FastAPI
from pydantic import BaseModel

from backend.utils import (
    extract_entities,
    generate_sql,
    normalize_schema,
)

from backend.er import generate_er

app = FastAPI()

class Request(BaseModel):
    text: str

@app.post("/generate")
def generate_schema(req: Request):
    try:
        entities, relationships, explanation, suggestions = extract_entities(req.text)

        if not entities:
            return {"error": "Failed to generate schema"}

        entities, relationships = normalize_schema(entities, relationships)

        sql = generate_sql(entities)

        try:
            er_path = generate_er(entities, relationships)
        except Exception:
            er_path = None

        return {
            "schema": entities,
            "relationships": relationships,
            "sql": sql,
            "er_diagram": er_path,
            "explanation": explanation,
            "suggestions": suggestions
        }

    except Exception as e:
        return {
            "error": "Internal server error",
            "details": str(e)
        }
