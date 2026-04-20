import json
import re

import requests


def extract_entities(text):
    prompt = f"""
You are a database designer.

Extract:
1. Entities with attributes
2. Relationships

Return ONLY JSON:

{{
  "entities": [
    {{
      "name": "Entity",
      "attributes": [
        "id",
        {{"name": "name", "type": "VARCHAR(255)"}}
      ]
    }}
  ],
  "relationships": [
    {{"from": "Entity1", "to": "Entity2", "type": "1:N"}}
  ],
  "explanation": "text",
  "suggestions": ["...", "..."]
}}

Rules:
- Use relationship types only as 1:1, 1:N, N:1, M:N, or M:1.
- Include foreign-key style attributes such as customer_id when they are clearly implied.
- Prefer data types DATE for dates and DECIMAL(10,2) for prices/totals when obvious.

System:
{text}
"""

    try:
        response = requests.post(
            "http://localhost:11434/api/generate",
            json={"model": "llama3", "prompt": prompt, "stream": False},
        )

        if response.status_code != 200:
            print("OLLAMA ERROR:", response.text)
            return [], [], "", []

        data = response.json()

        if "response" not in data:
            print("INVALID RESPONSE:", data)
            return [], [], "", []

        result = data["response"]

    except Exception as e:
        print("REQUEST ERROR:", e)
        return [], [], "", []

    try:
        result = result.strip()
        result = result.replace("```json", "").replace("```", "")

        match = re.search(r"\{.*\}", result, re.DOTALL)

        if not match:
            print("NO JSON FOUND:", result)
            return [], [], "", []

        parsed = json.loads(match.group(0))

        entities = parsed.get("entities", [])
        relationships = parsed.get("relationships", [])
        explanation = parsed.get("explanation", "")
        suggestions = parsed.get("suggestions", [])

        return entities, relationships, explanation, suggestions

    except Exception as e:
        print("PARSING ERROR:", e)
        print("RAW OUTPUT:", result)
        return [], [], "", []


def normalize_schema(entities, relationships):
    normalized_entities = []
    normalized_relationships = []

    for entity in entities:
        name = entity.get("name")
        if not name:
            continue

        normalized_attributes = []
        for attribute in entity.get("attributes", []):
            normalized_attributes.append(normalize_attribute(attribute))

        normalized_entity = {
            "name": name,
            "attributes": dedupe_attributes(normalized_attributes),
        }
        ensure_primary_key(normalized_entity)
        normalized_entities.append(normalized_entity)

    for rel in relationships:
        rel_from = rel.get("from")
        rel_to = rel.get("to")
        rel_type = normalize_relationship_type(rel.get("type", ""))

        if rel_from and rel_to and rel_type:
            normalized_relationships.append(
                {"from": rel_from, "to": rel_to, "type": rel_type}
            )

    apply_relationships(normalized_entities, normalized_relationships)
    return normalized_entities, normalized_relationships


def generate_sql(schema):
    queries = []

    for table in schema:
        column_definitions = []
        table_constraints = []
        composite_primary_key = []

        for attribute in table["attributes"]:
            column_name = attribute["name"]
            column_type = attribute.get("type", "VARCHAR(255)")
            parts = [column_name, column_type]

            if attribute.get("primary_key") and not attribute.get("part_of_composite_pk"):
                parts.append("PRIMARY KEY")

            if attribute.get("nullable") is False and not attribute.get("primary_key"):
                parts.append("NOT NULL")

            if attribute.get("unique"):
                parts.append("UNIQUE")

            column_definitions.append(" ".join(parts))

            if attribute.get("part_of_composite_pk"):
                composite_primary_key.append(column_name)

            foreign_key = attribute.get("foreign_key")
            if foreign_key:
                reference_column = foreign_key.get("column", "id")
                table_constraints.append(
                    f"FOREIGN KEY ({column_name}) REFERENCES "
                    f"{foreign_key['table']}({reference_column})"
                )

        if composite_primary_key:
            table_constraints.insert(
                0, f"PRIMARY KEY ({', '.join(composite_primary_key)})"
            )

        definition_lines = column_definitions + table_constraints
        query = (
            f"CREATE TABLE {table['name']} (\n  "
            + ",\n  ".join(definition_lines)
            + "\n);"
        )
        queries.append(query)

    return "\n\n".join(queries)


def normalize_attribute(attribute):
    if isinstance(attribute, dict):
        name = attribute.get("name")
        normalized = {
            "name": name,
            "type": normalize_data_type(attribute.get("type"), name),
            "primary_key": bool(attribute.get("primary_key", name == "id")),
            "nullable": attribute.get("nullable", name != "id"),
            "unique": bool(attribute.get("unique", False)),
        }

        if attribute.get("foreign_key"):
            normalized["foreign_key"] = attribute["foreign_key"]

        if attribute.get("part_of_composite_pk"):
            normalized["part_of_composite_pk"] = True
            normalized["nullable"] = False

        return normalized

    name = str(attribute)
    return {
        "name": name,
        "type": infer_data_type(name),
        "primary_key": name == "id",
        "nullable": name != "id",
        "unique": False,
    }


def normalize_data_type(data_type, attribute_name):
    if data_type:
        return data_type.upper()
    return infer_data_type(attribute_name)


def infer_data_type(attribute_name):
    name = (attribute_name or "").lower()

    if name == "id" or name.endswith("_id"):
        return "INT"
    if "date" in name or name.endswith("_at"):
        return "DATE"
    if any(token in name for token in ("price", "total", "amount", "cost")):
        return "DECIMAL(10,2)"
    if "description" in name or name.endswith("_text"):
        return "TEXT"
    return "VARCHAR(255)"


def dedupe_attributes(attributes):
    deduped = []
    seen = set()

    for attribute in attributes:
        name = attribute.get("name")
        if not name or name in seen:
            continue
        seen.add(name)
        deduped.append(attribute)

    return deduped


def ensure_primary_key(entity):
    for attribute in entity["attributes"]:
        if attribute.get("primary_key"):
            attribute["nullable"] = False
            return

    entity["attributes"].insert(
        0,
        {
            "name": "id",
            "type": "INT",
            "primary_key": True,
            "nullable": False,
            "unique": False,
        },
    )


def normalize_relationship_type(relationship_type):
    cleaned = relationship_type.upper().replace(" ", "")
    valid_types = {"1:1", "1:N", "N:1", "M:N", "N:M", "M:1", "1:M"}

    if cleaned not in valid_types:
        return None

    aliases = {"N:M": "M:N", "1:M": "1:N"}
    return aliases.get(cleaned, cleaned)


def apply_relationships(entities, relationships):
    entity_map = {entity["name"]: entity for entity in entities}

    for relationship in relationships:
        left = entity_map.get(relationship["from"])
        right = entity_map.get(relationship["to"])

        if not left or not right:
            continue

        rel_type = relationship["type"]

        if rel_type == "1:N":
            add_foreign_key(right, left)
        elif rel_type in {"N:1", "M:1"}:
            add_foreign_key(left, right)
        elif rel_type == "1:1":
            add_foreign_key(right, left, unique=True)
        elif rel_type == "M:N":
            join_table = build_join_table(left, right)
            if join_table["name"] not in entity_map:
                entities.append(join_table)
                entity_map[join_table["name"]] = join_table


def add_foreign_key(source_entity, target_entity, unique=False):
    fk_name = f"{target_entity['name'].lower()}_id"

    for attribute in source_entity["attributes"]:
        if attribute["name"] == fk_name:
            attribute["type"] = "INT"
            attribute["nullable"] = False
            attribute["foreign_key"] = {"table": target_entity["name"], "column": "id"}
            if unique:
                attribute["unique"] = True
            return

    source_entity["attributes"].append(
        {
            "name": fk_name,
            "type": "INT",
            "primary_key": False,
            "nullable": False,
            "unique": unique,
            "foreign_key": {"table": target_entity["name"], "column": "id"},
        }
    )


def build_join_table(left_entity, right_entity):
    left_fk = f"{left_entity['name'].lower()}_id"
    right_fk = f"{right_entity['name'].lower()}_id"

    return {
        "name": f"{left_entity['name']}{right_entity['name']}",
        "attributes": [
            {
                "name": left_fk,
                "type": "INT",
                "primary_key": False,
                "part_of_composite_pk": True,
                "nullable": False,
                "unique": False,
                "foreign_key": {"table": left_entity["name"], "column": "id"},
            },
            {
                "name": right_fk,
                "type": "INT",
                "primary_key": False,
                "part_of_composite_pk": True,
                "nullable": False,
                "unique": False,
                "foreign_key": {"table": right_entity["name"], "column": "id"},
            },
        ],
    }
