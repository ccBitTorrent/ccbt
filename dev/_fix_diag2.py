from pathlib import Path
import re

p = Path("ccbt/peer/async_peer_connection.py")
t = p.read_text(encoding="utf-8")
t2 = re.sub(
    r'"[^"]*CONNECTION DIAGNOSTICS: Total=%d',
    '"CONNECTION DIAGNOSTICS: Total=%d',
    t,
    count=1,
)
p.write_text(t2, encoding="utf-8")
