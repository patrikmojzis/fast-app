## storage

Facade over pluggable drivers with named disks and sensible defaults.

Defaults:
- `local`: `<cwd>/storage/local`
- `public`: `<cwd>/storage/public`

### Configure
```python
from fast_app.core.storage import Storage

Storage.configure({
  "s3": {"driver": "boto3", "bucket": "my-bucket", "region": "eu", "key": "...", "secret": "..."}
}, default_disk="s3")
```

Register drivers via `Storage.register_driver(name, cls)`; built‑ins are registered by `boot()`.

### Use
```python
from fast_app.core.storage import Storage

await Storage.put("uploads/file.txt", b"data")
exists = await Storage.exists("uploads/file.txt")
content = await Storage.get("uploads/file.txt")
resp = await Storage.download("uploads/file.txt", inline=False)
```
