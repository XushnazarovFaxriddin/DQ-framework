# Registry & Plugins

Registries (`src/runtime/registry.py`)

- Connectors: name → class
- Checks: name → class
- Alerts: name → function

Registration

- Decorators: `@register_connector(name)`, `@register_check(name)`, `@register_alert(name)`.
- Built‑ins are imported by `register_all()` which auto‑imports submodules under `src.connectors`, `src.checks`, `src.alerts`.
- Checks also support env controls (`src/checks/registry.py`):
  - `DQF_DISABLE_CHECKS`: comma‑separated to remove
  - `DQF_EXTRA_CHECKS`: comma‑separated module paths to import

Writing a plugin

```python
from src.runtime.registry import register_check
from src.checks.base import BaseCheck

@register_check("my_check")
class MyCheck(BaseCheck):
    def run(self):
        ...
```

Ship your module on `PYTHONPATH` and set `DQF_EXTRA_CHECKS=my_pkg.my_check_module`.

