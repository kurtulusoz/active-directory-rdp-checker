# AD Active RDP Session Checker

This project queries Active Directory computers, checks **RDP and WinRM port availability**, and exports the results into a CSV file.  
Additionally, it provides a simple web interface to view the generated CSV files.

---

## Components

- **ad-query**  
  Runs LDAP queries against Active Directory, resolves computer IPs, checks WinRM and RDP ports, and writes the results to `tools/output/rdp_check.csv`.

- **ad-query-scheduler**  
  Automatically runs the `ad-query` service every 5 minutes to keep the CSV file up to date.

- **csv-web**  
  A lightweight Ruby/Sinatra web service to serve CSV files.  
  If port mapping is enabled, you can browse the CSV results from your browser.

---

## Requirements

- Docker >= 27  
- Docker Compose >= v2.20  
- Active Directory access (LDAP + NTLM auth)  
- Windows machines with WinRM (5985/5986) and RDP (3389) ports open in the firewall  

---

## Setup & Usage

### 1. Clone the repository
```bash
git clone https://github.com/your-org/ad-active-rdp-session.git
cd ad-active-rdp-session
```

### 2. Create a `.env` file
Define your Active Directory connection details:

```env
AD_SERVER=ldap://your-ad-server.local
AD_USER=DOMAIN\username
AD_PASSWORD=yourpassword
AD_BASE_DN=DC=test,DC=local
AD_OUS=OU=Test1Clients,DC=test,DC=local;OU=Test2Clients,DC=test,DC=local
EXCLUDE=TestMachine,OldPC
```

- `AD_OUS` → separate multiple OUs with `;`  
- `EXCLUDE` → comma-separated list of machines to exclude  

### 3. Start with Docker Compose
```bash
docker compose up -d
```

### 4. Services
- `ad-query` → one-time LDAP/RDP check  
- `ad-query-scheduler` → runs every 5 minutes  
- `csv-web` → serves the CSV file via a web browser (if port is mapped, e.g. `http://localhost:8080`)

---

## Monitoring

Check logs:
```bash
docker logs -f ad-query
docker logs -f ad-query-scheduler
```

Check output CSV:
```bash
ls tools/output/rdp_check.csv
```

Access the web UI:
```bash
http://localhost:8080
```

---

## Project Structure

```
.
├── Dockerfile             # For ad-query service
├── docker-compose.yml     # Defines all services
├── tools/script/
│               └── query.py               # LDAP + RDP check script
│               └── sinatra_app.rb         # ruby script
├── tools/docker/
│               └── Dockerfile             # python dockerfile
│               └── ruby.Dockerfile        # ruby dockerfile               
├── tools/
│   └── output/            # CSV results
└── csv-web/               # Ruby Sinatra web service
```

---

## Example CSV Output

```csv
ComputerName,FQDN,IPAddress,WinRMPortOpen,RdpPortOpen,TargetUser,UserSessionStatus,CheckedAtUTC
CLX-DEV70,CLX-DEV70.test.local,192.168.1.50,True,True,test_common,Active,2025-08-21T11:35:25.314711+00:00
```
----
---
## Active Directory Configuration (Windows Server 2019+)

### Create a New OU
1. Open **Active Directory Users and Computers** (`dsa.msc`).
2. Right-click on the domain → **New → Organizational Unit (OU)**.
3. Name the OU (e.g., `Test1Clients`).
4. Move client computers into this OU:
   - Right-click the computer object → **Move** → select the OU.

### Enable WinRM & RDP on Clients

#### Via Group Policy (Recommended)
1. Open **Group Policy Management Console** (`gpmc.msc`).
2. Create a new GPO (e.g., `EnableWinRM_RDP`) and link it to the OU.
3. Configure policies:
   - **WinRM Service**:  
     `Computer Configuration → Policies → Administrative Templates → Windows Components → Windows Remote Management → Allow remote server management through WinRM`
   - **Firewall Rule for WinRM**:  
     `Computer Configuration → Policies → Windows Settings → Security Settings → Windows Firewall → Inbound Rules → Allow WinRM`
   - **Enable RDP**:  
     `Computer Configuration → Policies → Administrative Templates → Windows Components → Remote Desktop Services → Allow users to connect remotely`
4. Apply policy via:
   ```powershell
   gpupdate /force
   ```

#### Quick Test on a Single Machine
Run on client PowerShell (as Admin):
```powershell
Enable-PSRemoting -Force
Set-ItemProperty -Path "HKLM:\System\CurrentControlSet\Control\Terminal Server" -Name fDenyTSConnections -Value 0
Enable-NetFirewallRule -DisplayGroup "Remote Desktop"
Enable-NetFirewallRule -DisplayGroup "Windows Remote Management"
```

---

## Example Usage

After services are up:
- Query will run every 5 minutes and update `tools/output/rdp_check.csv`.
- Access results from your browser:
  ```
  http://localhost:8080/?path=rdp_check.csv
  ```

