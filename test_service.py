import json

from app.service import investigate_target


result = investigate_target("github.com")

print(
    json.dumps(
        result.model_dump(),
        indent=2
    )
)