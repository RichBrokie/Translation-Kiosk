import sys
import importlib

packages_to_check = [
    # Testing
    'pytest', 'pytest_asyncio', 'unittest', 'mock',
    # HTTP & WebSockets
    'httpx', 'websockets', 'aiohttp', 'requests', 'urllib3',
    # Web Frameworks
    'fastapi', 'uvicorn', 'starlette', 'pydantic', 'pydantic_settings', 'jinja2', 'multipart',
    # Audio Processing & ML
    'soundfile', 'scipy', 'scipy.io.wavfile', 'scipy.signal', 'wave', 'faster_whisper', 'torchaudio', 'torch',
    # LLM & AI
    'openai', 'vllm', 'transformers', 'tokenizers',
    # Utilities & Monitoring
    'psutil', 'prometheus_client', 'loguru', 'rich', 'watchfiles'
]

print(f"{'Package':<25} | {'Status':<15} | {'Version':<20}")
print("-" * 65)

for pkg in packages_to_check:
    try:
        mod = importlib.import_module(pkg)
        ver = getattr(mod, '__version__', 'Installed')
        print(f"{pkg:<25} | {'AVAILABLE':<15} | {str(ver):<20}")
    except Exception as e:
        print(f"{pkg:<25} | {'MISSING':<15} | {str(e)[:20]}")

