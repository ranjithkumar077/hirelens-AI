import urllib.error
import urllib.request

boundary = "----hirelens"
jd = b"Python ML engineer needs AWS Docker Kubernetes and 2 years experience. " * 4
resume = b"Student intern with Python SQL academic projects only. " * 4


def part(name: str, filename: str, body: bytes) -> bytes:
    header = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="{name}"; filename="{filename}"\r\n'
        "Content-Type: text/plain\r\n\r\n"
    ).encode()
    return header + body + b"\r\n"


body = part("jd", "jd.txt", jd) + part("resume", "resume.txt", resume) + f"--{boundary}--\r\n".encode()
req = urllib.request.Request(
    "http://127.0.0.1:8080/api/analyze",
    data=body,
    headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
)
try:
    print(urllib.request.urlopen(req, timeout=30).read()[:300])
except urllib.error.HTTPError as exc:
    print(exc.code, exc.read().decode()[:500])
