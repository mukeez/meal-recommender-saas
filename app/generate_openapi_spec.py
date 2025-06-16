from main import app
import yaml

openapi_dict = app.openapi()
with open("openapi.yaml", "w") as f:
    yaml.dump(openapi_dict, f, default_flow_style=False)