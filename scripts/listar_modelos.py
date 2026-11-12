"""Lista los modelos disponibles para TU clave en el endpoint configurado en .env."""

import os
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()
c = OpenAI(base_url=os.getenv("LLM_BASE_URL"), api_key=os.getenv("LLM_API_KEY"))
for m in sorted(x.id for x in c.models.list().data):
    print(m)
