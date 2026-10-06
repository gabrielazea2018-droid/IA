from backend.main import app

spec = app.openapi()
for p, ops in sorted(spec["paths"].items()):
    for m, op in ops.items():
        print(f"{m.upper():7} {p:30} {op.get('summary', '')}")
print()
print("docs:", app.docs_url, "| redoc:", app.redoc_url, "| openapi:", app.openapi_url)
