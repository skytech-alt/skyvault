#!/usr/bin/env python3
"""
SkyVault — проверка синтаксиса + деплой в GitHub через REST API (без git).

Использование:
    python deploy_skyvault.py                    # создать/использовать 'skyvault'
    python deploy_skyvault.py --name myapp       # другое имя репо
    python deploy_skyvault.py --private          # приватный репо
    python deploy_skyvault.py -m "Fix contacts"  # своё сообщение коммита
    python deploy_skyvault.py --skip-push        # только тесты
    python deploy_skyvault.py --repo URL         # пуш в готовый репо (owner/name в URL)
    python deploy_skyvault.py --clean            # удалить на remote файлы, которых нет локально

Требования:
    - Python 3.8+
    - token.txt рядом со скриптом
    - Classic PAT: scope 'repo'
      Fine-grained: Contents:RW + Repository creation:RW + Workflows:RW
"""

import argparse
import base64
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
TOKEN_FILE = PROJECT_ROOT / "token.txt"
API = "https://api.github.com"

IGNORE_DIRS = {
    "venv", ".venv", "env", ".buildozer", "bin", "build", "dist",
    "__pycache__", ".git", ".idea", ".vscode", ".pytest_cache",
    "node_modules", ".mypy_cache", ".tox",
}

# Что не заливаем на GitHub
SKIP_FILES = {"token.txt", "deploy_skyvault.py", "generate_skyvault.py"}

# Расширения, которые заливаем (текстовые)
UPLOAD_EXTS = {".py", ".kv", ".spec", ".txt", ".md", ".yml", ".yaml",
               ".json", ".cfg", ".ini", ".toml", ".gitignore", ""}

MAX_FILE_BYTES = 2 * 1024 * 1024  # 2 MB

WORKFLOW_YML = """name: Build Kivy APK

on:
  push:
    branches: [ main, master ]
  workflow_dispatch:

jobs:
  build-android:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Build with Buildozer
        uses: ArtemSBulgakov/buildozer-action@v1
        id: buildozer
        with:
          command: android debug
          buildozer_version: master
      - name: Upload APK
        uses: actions/upload-artifact@v4
        with:
          name: skyvault-apk
          path: ${{ steps.buildozer.outputs.filename }}
"""


# ==========================================================
# Проверки
# ==========================================================


def find_files():
    found = []
    for p in PROJECT_ROOT.rglob("*"):
        if not p.is_file():
            continue
        rel = p.relative_to(PROJECT_ROOT)
        if any(part in IGNORE_DIRS for part in rel.parts):
            continue
        if p.name in SKIP_FILES:
            continue
        if p.suffix.lower() not in UPLOAD_EXTS and p.name != ".gitignore":
            continue
        found.append(p)
    return sorted(found)


def check_python(files):
    errors = []
    for f in files:
        if f.suffix != ".py":
            continue
        try:
            with open(f, "rb") as fp:
                compile(fp.read(), str(f), "exec")
        except SyntaxError as e:
            errors.append((f, f"строка {e.lineno or '?'}: {e.msg}"))
        except Exception as e:  # noqa: BLE001
            errors.append((f, str(e)))
    return errors


def _balance_error(text):
    pairs = {"}": "{", "]": "[", ")": "("}
    stack, line, in_str, prev = [], 1, None, ""
    for ch in text:
        if ch == "\n":
            line += 1
            in_str, prev = None, ""
            continue
        if in_str:
            if ch == in_str and prev != "\\":
                in_str = None
            prev = ch
            continue
        if ch in ("'", '"'):
            in_str, prev = ch, ch
            continue
        if ch in "{([":
            stack.append((ch, line))
        elif ch in "})]":
            if not stack or stack[-1][0] != pairs[ch]:
                return f"лишняя {ch!r} на строке {line}"
            stack.pop()
        prev = ch
    if stack:
        ch, ln = stack[-1]
        return f"незакрытая {ch!r} со строки {ln}"
    return None


def check_kv(files):
    try:
        from kivy.lang.parser import Parser  # type: ignore
        has_kivy = True
    except Exception:  # noqa: BLE001
        has_kivy = False
        print("  [i] Kivy не установлен — базовая проверка скобок")
    errors = []
    for f in files:
        if f.suffix != ".kv":
            continue
        try:
            content = f.read_text(encoding="utf-8")
        except Exception as e:  # noqa: BLE001
            errors.append((f, f"не читается: {e}"))
            continue
        if has_kivy:
            try:
                Parser(content=content, filename=str(f))
            except Exception as e:  # noqa: BLE001
                errors.append((f, str(e).split("\n")[0]))
        else:
            err = _balance_error(content)
            if err:
                errors.append((f, err))
    return errors


def check_buildozer_spec():
    spec = PROJECT_ROOT / "buildozer.spec"
    if not spec.exists():
        return [("buildozer.spec", "файл не найден")]
    content = spec.read_text(encoding="utf-8")
    errors = []
    if "[app]" not in content:
        errors.append(("buildozer.spec", "нет секции [app]"))
    for key in ("title", "package.name", "package.domain", "requirements"):
        if f"{key} =" not in content:
            errors.append(("buildozer.spec", f"нет ключа '{key}'"))
    return errors


# ==========================================================
# GitHub REST
# ==========================================================


def api(method, path, token, data=None):
    """Запрос к GitHub API. Возвращает (status, dict)."""
    url = path if path.startswith("http") else f"{API}{path}"
    req = urllib.request.Request(url, method=method)
    req.add_header("Authorization", f"token {token}")
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("X-GitHub-Api-Version", "2022-11-28")
    req.add_header("User-Agent", "SkyVault-Deployer")
    if data is not None:
        req.data = json.dumps(data).encode("utf-8")
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            body = r.read().decode("utf-8", errors="replace")
            try:
                return r.status, json.loads(body)
            except Exception:  # noqa: BLE001
                return r.status, {"raw": body}
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        try:
            return e.code, json.loads(body)
        except Exception:  # noqa: BLE001
            return e.code, {"raw": body}
    except urllib.error.URLError as e:
        return 0, {"error": str(e.reason)}


def get_login(token):
    s, d = api("GET", "/user", token)
    if s == 200:
        return d["login"], None
    if s == 401:
        return None, "неверный токен (HTTP 401)"
    return None, f"GET /user: HTTP {s}: {d.get('message', d)}"


def create_or_get_repo(token, login, name, private=False):
    """POST /user/repos. 409/422 'already exists' — не ошибка."""
    payload = {
        "name": name,
        "private": bool(private),
        "auto_init": False,
        "description": "SkyVault — офлайн-хранилище личных данных",
        "default_branch": "main",
    }
    status, data = api("POST", "/user/repos", token, payload)
    owner = data.get("owner", {}).get("login", login) if status == 201 else login
    repo_name = data.get("name", name) if status == 201 else name

    if status == 201:
        print(f"  [+] Репозиторий создан: {data.get('html_url')}")
        return owner, repo_name, True, None

    if status in (409, 422):
        msg = str(data.get("message", "")).lower()
        errs = " ".join(str(e.get("message", "")) for e in data.get("errors", [])).lower()
        if status == 409 or "already exists" in msg or "already exists" in errs:
            print(f"  [i] Репозиторий уже существует — использую {owner}/{repo_name}")
            return owner, repo_name, False, None

    if status == 404:
        return None, None, False, (
            "HTTP 404. Причины: токен без прав на создание репо, "
            "либо он не покрывает организацию (для орг нужен SSO)."
        )

    return None, None, False, f"HTTP {status}: {data.get('message', data)}"


def get_default_branch(token, owner, repo):
    s, d = api("GET", f"/repos/{owner}/{repo}", token)
    if s == 200:
        return d.get("default_branch", "main")
    return "main"


def get_branch_sha(token, owner, repo, branch):
    """Возвращает (commit_sha или None, tree_sha или None)."""
    s, d = api("GET", f"/repos/{owner}/{repo}/git/ref/heads/{branch}", token)
    if s == 404:
        return None, None
    if s != 200:
        return None, None
    commit_sha = d["object"]["sha"]
    s2, d2 = api("GET", f"/repos/{owner}/{repo}/git/commits/{commit_sha}", token)
    if s2 != 200:
        return commit_sha, None
    return commit_sha, d2["tree"]["sha"]


def get_remote_tree_paths(token, owner, repo, tree_sha):
    """Возвращает множество путей файлов на remote (для --clean)."""
    s, d = api("GET", f"/repos/{owner}/{repo}/git/trees/{tree_sha}?recursive=1", token)
    if s != 200:
        return set()
    return {item["path"] for item in d.get("tree", []) if item.get("type") == "blob"}


# ==========================================================
# Сборка файлов
# ==========================================================


def read_text_file(path):
    """Читает файл как UTF-8; при ошибке — None (бинарник пропускаем)."""
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return None
    except Exception as e:  # noqa: BLE001
        print(f"  [!] Пропуск {path.name}: {e}")
        return None


def build_tree_items(files, token, owner, repo, base_tree_paths, clean=False):
    """Возвращает (items для tree API, список удаляемых путей, предупреждения)."""
    items = []
    warnings = []
    local_paths = set()

    for f in files:
        rel = f.relative_to(PROJECT_ROOT).as_posix()
        if f.stat().st_size > MAX_FILE_BYTES:
            warnings.append(f"{rel}: {f.stat().st_size} байт > 2 MB — пропуск")
            continue
        text = read_text_file(f)
        if text is None:
            warnings.append(f"{rel}: бинарный файл — пропуск")
            continue
        items.append({
            "path": rel,
            "mode": "100644",
            "type": "blob",
            "content": text,
        })
        local_paths.add(rel)

    # Автодобавление workflow
    wf_path = ".github/workflows/build.yml"
    if wf_path not in local_paths:
        items.append({
            "path": wf_path,
            "mode": "100644",
            "type": "blob",
            "content": WORKFLOW_YML,
        })
        local_paths.add(wf_path)
        print(f"  [+] Добавлен {wf_path} (сборка APK через GitHub Actions)")

    to_delete = []
    if clean and base_tree_paths:
        for rp in base_tree_paths - local_paths:
            to_delete.append(rp)

    return items, to_delete, warnings


# ==========================================================
# API-операции записи
# ==========================================================


def init_empty_repo(token, owner, repo, items, message, branch):
    """
    Инициализирует пустой репозиторий, создавая первый файл через Contents API.
    Возвращает (ok, updated_items, error_msg).
    """
    if not items:
        return False, items, "нечего создавать: список файлов пуст"

    # Якорь: README.md, иначе первый файл из списка
    init_item = None
    for it in items:
        if it["path"] == "README.md":
            init_item = it
            break
    if init_item is None:
        init_item = items[0]

    print(f"  [i] Репозиторий пуст — инициализирую через Contents API ({init_item['path']})")

    content_b64 = base64.b64encode(init_item["content"].encode("utf-8")).decode("ascii")
    payload = {
        "message": message,
        "content": content_b64,
        "branch": branch,
    }
    status, data = api(
        "PUT",
        f"/repos/{owner}/{repo}/contents/{init_item['path']}",
        token,
        payload,
    )
    if status not in (200, 201):
        return False, items, f"init via Contents API: HTTP {status}: {data.get('message', data)}"

    print(f"  [+] Первый файл создан: {init_item['path']}")

    updated_items = [it for it in items if it["path"] != init_item["path"]]
    return True, updated_items, None


def push_all_files(token, owner, repo, items, to_delete, message, branch):
    """
    Один атомарный коммит: tree → commit → ref.
    Автоматически инициализирует пустой репозиторий через Contents API.
    """
    # 1. Текущее состояние
    parent_sha, base_tree_sha = get_branch_sha(token, owner, repo, branch)

    # 2. Если репозиторий пуст — инициализация через Contents API
    if parent_sha is None:
        ok, items, err = init_empty_repo(token, owner, repo, items, message, branch)
        if not ok:
            return False, err
        parent_sha, base_tree_sha = get_branch_sha(token, owner, repo, branch)
        if parent_sha is None:
            return False, "репозиторий не инициализировался после Contents API"

    # Если после инициализации нечего добавлять/удалять — коммит уже создан
    if not items and not to_delete:
        return True, f"инициализирован первым файлом (ветка {branch})"

    # 3. Пути на remote (для base_tree и --clean)
    base_paths = set()
    if base_tree_sha:
        base_paths = get_remote_tree_paths(token, owner, repo, base_tree_sha)

    # 4. Проставить null-content для удаляемых
    tree_items = list(items)
    for p in to_delete:
        tree_items.append({"path": p, "mode": "100644", "type": "blob", "sha": None})
    if to_delete:
        print(f"  [i] Удаляю с remote: {len(to_delete)} файл(ов)")

    # 5. Создать tree
    payload = {"tree": tree_items}
    if base_tree_sha:
        payload["base_tree"] = base_tree_sha
    status, data = api("POST", f"/repos/{owner}/{repo}/git/trees", token, payload)
    if status not in (200, 201):
        return False, f"create tree: HTTP {status}: {data.get('message', data)}"
    new_tree = data["sha"]

    # 6. Создать commit
    commit_payload = {
        "message": message,
        "tree": new_tree,
        "parents": [parent_sha],
    }
    status, data = api("POST", f"/repos/{owner}/{repo}/git/commits", token, commit_payload)
    if status not in (200, 201):
        return False, f"create commit: HTTP {status}: {data.get('message', data)}"
    new_commit = data["sha"]

    # 7. Обновить ref (ветка уже существует после инициализации)
    status, data = api(
        "PATCH",
        f"/repos/{owner}/{repo}/git/refs/heads/{branch}",
        token,
        {"sha": new_commit, "force": False},
    )
    if status not in (200, 201):
        return False, f"update ref: HTTP {status}: {data.get('message', data)}"

    return True, f"запушено {len(items)} файл(ов) → {branch} ({new_commit[:7]})"


# ==========================================================
# main
# ==========================================================


def parse_owner_repo(url):
    """https://github.com/O/R(.git) → (O, R)."""
    u = url.strip().rstrip("/")
    if u.endswith(".git"):
        u = u[:-4]
    if u.startswith("https://github.com/"):
        u = u[len("https://github.com/"):]
    elif u.startswith("github.com/"):
        u = u[len("github.com/"):]
    if "/" not in u:
        return None, None
    owner, repo = u.split("/", 1)
    if "/" in repo:
        return None, None
    return owner, repo


def main():
    ap = argparse.ArgumentParser(
        description="SkyVault: проверка синтаксиса + деплой в GitHub (без git)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument("--name", default="skyvault", help="Имя репозитория")
    ap.add_argument("--repo", help="Готовый URL (https://github.com/O/R)")
    ap.add_argument("--private", action="store_true", help="Приватный репозиторий")
    ap.add_argument("-m", "--message", default="SkyVault update", help="Сообщение коммита")
    ap.add_argument("--skip-push", action="store_true", help="Только проверки")
    ap.add_argument("--clean", action="store_true", help="Удалять на remote отсутствующие локально файлы")
    args = ap.parse_args()

    print("=" * 62)
    print(" SkyVault — проверка + деплой (GitHub REST API, без git)")
    print("=" * 62)
    print(f" Проект: {PROJECT_ROOT}\n")

    files = find_files()
    if not files:
        print("✗ Не найдено файлов для загрузки")
        return 1

    # 1. Python
    print("[1/3] Синтаксис Python...")
    errs = check_python(files)
    if errs:
        print(f"  ✗ {len(errs)} ошибок:")
        for f, m in errs:
            print(f"    {f.relative_to(PROJECT_ROOT)}: {m}")
        return 1
    print(f"  ✓ OK ({sum(1 for f in files if f.suffix == '.py')} файлов)\n")

    # 2. KV
    print("[2/3] Синтаксис .kv...")
    errs = check_kv(files)
    if errs:
        print(f"  ✗ {len(errs)} ошибок:")
        for f, m in errs:
            print(f"    {f.relative_to(PROJECT_ROOT)}: {m}")
        return 1
    print(f"  ✓ OK ({sum(1 for f in files if f.suffix == '.kv')} файлов)\n")

    # 3. buildozer.spec
    print("[3/3] buildozer.spec...")
    errs = check_buildozer_spec()
    if errs:
        for _, m in errs:
            print(f"    ✗ {m}")
        return 1
    print("  ✓ OK\n")

    if args.skip_push:
        print("Проверки пройдены. Пуш пропущен (--skip-push).")
        return 0

    # 4. Токен
    print("[+] Деплой в GitHub")
    if not TOKEN_FILE.exists():
        print(f"  ✗ '{TOKEN_FILE.name}' не найден рядом со скриптом")
        return 1
    token = TOKEN_FILE.read_text(encoding="utf-8").strip()
    if not token:
        print(f"  ✗ '{TOKEN_FILE.name}' пуст")
        return 1
    print(f"  Токен: {len(token)} символов")

    # 5. Owner/repo
    if args.repo:
        owner, repo = parse_owner_repo(args.repo)
        if not owner:
            print(f"  ✗ Не удалось разобрать URL: {args.repo}")
            return 1
        print(f"  [i] Использую готовый: {owner}/{repo}")
    else:
        login, err = get_login(token)
        if err:
            print(f"  ✗ {err}")
            return 1
        print(f"  Пользователь: {login}")
        owner, repo, _, err = create_or_get_repo(
            token, login, args.name, private=args.private)
        if err:
            print(f"  ✗ {err}")
            return 1

    # 6. Ветка
    branch = get_default_branch(token, owner, repo)
    print(f"  Ветка: {branch}")

    # 7. Что на remote
    parent_sha, base_tree_sha = get_branch_sha(token, owner, repo, branch)
    base_paths = set()
    if base_tree_sha:
        base_paths = get_remote_tree_paths(token, owner, repo, base_tree_sha)
        print(f"  На remote: {len(base_paths)} файл(ов)")
    else:
        print("  Remote пуст — будет первый коммит")

    # 8. Собрать tree items
    items, to_delete, warnings = build_tree_items(
        files, token, owner, repo, base_paths, clean=args.clean)
    for w in warnings:
        print(f"  [!] {w}")

    # 9. Пуш
    ok, msg = push_all_files(
        token, owner, repo, items, to_delete, args.message, branch)
    if not ok:
        print(f"  ✗ {msg}")
        return 1
    print(f"  ✓ {msg}\n")
    print("=" * 62)
    print(f" Готово → https://github.com/{owner}/{repo}")
    print("=" * 62)
    return 0


if __name__ == "__main__":
    sys.exit(main())