import importlib, inspect
m = importlib.import_module("pdf_processor")
print("pdf_processor OK:", m is not None)
for name in ("extract_data_from_pdf","parse_pdf_to_data","build_data_from_pdf","parse"):
    f = getattr(m, name, None)
    print(name, "=>", callable(f))
    if callable(f):
        print("sig:", inspect.signature(f))
