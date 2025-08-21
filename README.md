# AD Active RDP Session Checker

Lists computers from specified OUs in Active Directory, checks **WinRM (5985)** and **RDP (3389)** reachability, and detects whether the target user has an active/disconnected session. Results are written to a CSV file and can be viewed via a lightweight Sinatra web UI.

---

## 🚀 Components (as defined in `docker-compose.yml`)

- **ad-query** — Built from `tools/docker/Dockerfile`. Runs `tools/script/query.py` inside the container and writes `rdp_check.csv` under `/app/output` (shared named volume).
- **csv-web** — Built from `tools/docker/ruby.Dockerfile`. Runs the Sinatra app at `tools/script/sinatra_app.rb` to render the CSV at `http://localhost:8080/`.
- **(optional) ad-query-scheduler** — Uses the Docker CLI image to trigger `ad-query` every 5 minutes (`docker compose run --rm ad-query`). Mounts `docker.sock` → consider the security notes below.

---

## 📂 Project Structure

```text
.
├─ docker-compose.yml
├─ tools/
│  ├─ docker/
│  │  ├─ Dockerfile          # image for ad-query
│  │  └─ ruby.Dockerfile     # image for csv-web
│  └─ script/
│     ├─ query.py            # main AD/WinRM/RDP checker
│     └─ sinatra_app.rb      # Sinatra web app
├─ output/                   # runtime data (mapped to a named volume)
├─ .env.example
├─ .gitignore
├─ .dockerignore
└─ README.md
```

---

## ⚙️ Environment (`.env`)

Fill in **your own** AD details and runtime knobs (values below are examples):

```env
AD_USERNAME=administrator
AD_PASSWORD=PASSWORD
AD_DOMAIN=domain.local
AD_SERVER=192.0.2.10
AD_NETBIOS=DOMAIN

# Optional knobs that you may also pass via compose 'command:'
TIMEOUT_SECONDS=5
TARGET_USER=check_remote_user
EXCLUDE_COMPUTERS=HOST1 HOST2 NASX

# One or more OUs (quote each OU DN separately):
OUs="OU=Test1Clients,DC=test,DC=local" "OU=Test2Clients,DC=test,DC=local"
```

In the current compose, the **AD\_*** variables are read from `.env` and injected via `environment:`. The query parameters (`--TargetUser`, `--OUs`, `--ExcludeComputers`, `--TimeoutSeconds`) are passed directly in the `command:` field. You can keep this or refactor to read them from the `.env` variables above.

---

## ▶️ Run

Build and start all services:

```bash
docker compose up -d --build
```

What happens:

- **ad-query** runs with the configured command and writes the CSV to the shared volume.
- **csv-web** starts at <http://localhost:8080/> and serves the CSV.
- **(optional) ad-query-scheduler** triggers `ad-query` every **5 minutes** using `docker compose run --rm ad-query`.

Stop everything:

```bash
docker compose down
```

---

## 🌍 Web Interface (Sinatra)

The Ruby app lives at `tools/script/sinatra_app.rb` and is built by `tools/docker/ruby.Dockerfile`.

- Table view: <http://localhost:8080/>
- Raw CSV: <http://localhost:8080/raw?path=rdp_check.csv>
- Latest shortcut (if enabled in the app): <http://localhost:8080/latest>

> `csv-web` mounts the output volume as **read-only**; its own log file is written under `/tmp/csv_web.log` inside the container.

---

## 📊 Output & Volume

- CSV path inside containers:
  ```
  /app/output/rdp_check.csv
  ```
- Shared named volume: see `volumes:` section in `docker-compose.yml` (e.g. `output_data` named `ad_active_rdp_session_output`).
- Copy to host (example):
  ```bash
  docker cp ad-query-container:/app/output/rdp_check.csv ./rdp_check.csv
  ```

---

## 🔐 Security Notes

- **Never commit** your `.env` file.
- Prefer **LDAPS:636** for LDAP and **HTTPS:5986** for WinRM where possible.
- The scheduler mounts **/var/run/docker.sock**; keep it **optional** and enable only in trusted environments.

---

## 🧩 Compose Hints

- Multiple OUs are passed as **separate quoted arguments** after `--OUs`:
  ```yaml
  --OUs "OU=CityA,DC=domain,DC=local"
       "OU=CityB,DC=domain,DC=local"
  ```
- `ad-query` service sets `dns` so LDAP hostname resolution can route via your DC first.
- Healthchecks are included for faster failure surfacing.

---

## 📄 License

MIT License
