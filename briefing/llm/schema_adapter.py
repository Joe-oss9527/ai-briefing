"""Minimal schema adapter for LLM providers."""

def to_gemini(schema: dict) -> dict:
    """Convert JSON Schema to Gemini response_schema format."""
    TYPE_MAP = {
        "object": "OBJECT",
        "string": "STRING",
        "array": "ARRAY",
        "number": "NUMBER",
        "integer": "INTEGER",
        "boolean": "BOOLEAN"
    }
    
    def convert(node):
        if not isinstance(node, dict):
            return node
            
        result = {}
        
        # Convert type
        if "type" in node:
            result["type"] = TYPE_MAP.get(node["type"], node["type"])
        
        # Handle properties with ordering
        if "properties" in node:
            result["properties"] = {
                k: convert(v) for k, v in node["properties"].items()
            }
            result["propertyOrdering"] = list(node["properties"].keys())
        
        # Handle array items
        if "items" in node:
            result["items"] = convert(node["items"])
        
        # Copy constraints
        for key in ["required", "minItems", "maxItems", "minLength", "format"]:
            if key in node:
                result[key] = node[key]
        
        # Force additionalProperties false for objects
        if result.get("type") == "OBJECT":
            result["additionalProperties"] = False
            
        return result
    
    # Remove $schema and convert
    clean = {k: v for k, v in schema.items() if k != "$schema"}
    return convert(clean)

def to_openai(schema: dict) -> dict:
    """Prepare schema for OpenAI (just remove $schema)."""
    return {k: v for k, v in schema.items() if k != "$schema"}