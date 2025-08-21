#!/usr/bin/env python3
import argparse
import datetime
from datetime import UTC
import os
import socket
import sys
from typing import Dict, List, Tuple

from ldap3 import Server, Connection, ALL, NTLM, SIMPLE
from ldap3.utils.dn import parse_dn, LDAPInvalidDnError
import pandas as pd
from tqdm import tqdm
import winrm


# ------- Argümanlar -------
parser = argparse.ArgumentParser(
    description="IP and RDP session control for machines inside AD OUs"
)
parser.add_argument("--TargetUser", required=True, help="User to be checked (domain user)")
parser.add_argument("--Domain", required=True, help="AD FQDN (e.g., test.local)")
parser.add_argument(
    "--OUs",
    nargs="+",
    required=True,
    help='One or more OUs. Example: --OUs "OU=Test1Clients,DC=test,DC=local" "OU=Test2Clients,DC=test,DC=local"',
)
parser.add_argument("--ExcludeComputers", nargs="*", default=[], help="Computer names to be excluded")
parser.add_argument("--TimeoutSeconds", type=float, default=2.0, help="TCP connection timeout (s)")
args = parser.parse_args()


# ------- Ortam değişkenleri -------
ad_username_raw = os.getenv("AD_USERNAME")
ad_password     = os.getenv("AD_PASSWORD")
ad_domain       = os.getenv("AD_DOMAIN") or args.Domain        # FQDN (test.local)
ad_server       = os.getenv("AD_SERVER")                       # DC/DNS IP veya FQDN
ad_netbios      = os.getenv("AD_NETBIOS")                      # Short domain (e.g., test) — optional

if not all([ad_username_raw, ad_password, ad_server]):
    print("ERROR: AD\_USERNAME, AD\_PASSWORD, and AD\_SERVER environment variables are required.", file=sys.stderr)
    sys.exit(2)


# ------- Yardımcılar -------
def split_domain_user(u: str) -> Tuple[str | None, str, str]:
    """
    DOMAIN\user, user\@fqdn or just user -> (netbios\_or\_none, user\_only, upn)
    """
    if "\\" in u:
        dom, usr = u.split("\\", 1)
        upn = f"{usr}@{ad_domain}"
        return dom, usr, upn
    if "@" in u:
        usr, _ = u.split("@", 1)
        upn = u
        return None, usr, upn
    usr = u
    upn = f"{usr}@{ad_domain}"
    return None, usr, upn


def is_valid_dn(dn: str) -> bool:
    try:
        parse_dn(dn, escape=True)
        return True
    except LDAPInvalidDnError:
        return False


nb, user_only, upn_user = split_domain_user(ad_username_raw)
# NetBIOS domain: if not provided from .env, derive from FQDN (test.local -> test)
if not ad_netbios:
    ad_netbios = (ad_domain.split(".")[0] if "." in ad_domain else ad_domain).upper()

# DOMAIN\user for NTLM bind
bind_user_ntlm = f"{(nb or ad_netbios)}\\{user_only}"
# UPN for SIMPLE bind
bind_user_upn = upn_user


def tcp_up(host: str, port: int, timeout: float) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except Exception:
        return False


def resolve_hostnames(name: str) -> str:
    """
    dNSHostName -> FQDN -> NetBIOS, tries to resolve in order.
    Return: IPv4 string or 'N/A'
    """
    candidates = []
    if "." in name:
        candidates.append(name)
        candidates.append(name.split(".")[0])
    else:
        candidates.append(f"{name}.{ad_domain}")
        candidates.append(name)

    for host in candidates:
        try:
            return socket.gethostbyname(host)
        except Exception:
            continue
    return "N/A"


def ldap_bind() -> Connection:
    """
    Connect to LDAP: first NTLM (DOMAIN\user), if not, then SIMPLE (UPN).
    """
    server = Server(ad_server, get_info=ALL)
    try:
        return Connection(
            server,
            user=bind_user_ntlm,
            password=ad_password,
            authentication=NTLM,
            auto_bind=True,
        )
    except Exception:
        return Connection(
            server,
            user=bind_user_upn,
            password=ad_password,
            authentication=SIMPLE,
            auto_bind=True,
        )


def get_ldap_computers(conn: Connection, ou: str, exclude: List[str]) -> List[Dict]:
    """
    Returns computer objects under a specific OU:
    [{"ComputerName": ..., "DnsHostName": ...}, ...]
    """
    search_filter = "(&(objectCategory=computer))"
    conn.search(
        search_base=ou,
        search_filter=search_filter,
        attributes=["name", "dNSHostName", "operatingSystem", "lastLogonTimestamp"],
    )

    results = []
    for entry in conn.entries:
        name = str(entry.name)
        if name.upper() in [e.upper() for e in exclude]:
            continue
        dnsk = str(entry.dNSHostName) if hasattr(entry, "dNSHostName") else ""
        results.append({"ComputerName": name, "DnsHostName": dnsk})
    return results


def winrm_quser(ip: str, domain_user: str, timeout: float) -> str:
    """
    Opens a WinRM session with NTLM and runs quser/query user.
    Returned string:
        'Active RDP session' / 'Disconnected RDP session' / 'No session found'
        or error message.
    """
    try:
        session = winrm.Session(
            f"http://{ip}:5985/wsman",
            auth=(bind_user_ntlm, ad_password),
            transport="ntlm",
            read_timeout_sec=max(10, int(timeout * 10)),
            operation_timeout_sec=max(8, int(timeout * 8)),
        )

        ps = r'$out = quser 2>$null; if ($LASTEXITCODE -ne $null) { $out }'
        result = session.run_ps(ps)

        if result.status_code != 0 or not result.std_out:
            result = session.run_cmd("query", ["user"])

        if result.status_code == 0:
            output = (result.std_out or b"").decode(errors="ignore")
            if not output.strip():
                return "No session found"
            for line in output.splitlines():
                low = line.lower()
                if domain_user.lower() in low and ("rdp-tcp" in low or "rdp-tcp#" in low):
                    if "active" in low:
                        return "Active RDP session"
                    if "disc" in low or "disconnected" in low:
                        return "Disconnected RDP session"
            return "No session found"
        else:
            err = (result.std_err or b"").decode(errors="ignore").strip()
            return f"quser failed: {err}" if err else "quser failed: status!=0"
    except Exception as e:
        return f"Error: {e}"


def normalize_ou_list(raw_items):
    """Clean OU arguments: empty ones, only commas, trailing extra commas, etc."""
    cleaned = []
    for it in raw_items:
        if it is None:
            continue
        s = it.strip()
        if not s:
            continue
        # In some compose definitions, a ',' is mistakenly added at the end of the OU value.
        # A normal DN never ends with ','; we can safely trim it.
        if s.endswith(','):
            s = s[:-1].strip()
        # If it consists only of a comma, discard it.
        if set(s) == {','}:
            continue
        cleaned.append(s)
    return cleaned

# ------- Main flow. -------
def main():
    exclude = args.ExcludeComputers or []
    timeout = args.TimeoutSeconds

    # Sanitize the OU list.
    ou_list = normalize_ou_list(args.OUs)
    print(f"[{datetime.datetime.now(UTC).isoformat()}] OU(s) searching: {', '.join(ou_list)}")

    # LDAP bind
    conn = ldap_bind()

    # Collect machines from multiple OUs.
    machines: Dict[str, Dict] = {}
    for ou in ou_list:
        if not is_valid_dn(ou):
            print(f"\[WARN] Invalid DN skipped: {ou!r}")
            continue
        try:
            raw = get_ldap_computers(conn, ou, exclude)
        except LDAPInvalidDnError:
            print(f"\[WARN] Failed to parse DN, skipped: {ou!r}")
            continue
        for item in raw:
            machines[item['ComputerName']] = item

    # Name -> IP mapping.
    name_to_ip: Dict[str, str] = {}
    for item in machines.values():
        candidate = item["DnsHostName"] or item["ComputerName"]
        name_to_ip[item["ComputerName"]] = resolve_hostnames(candidate)

    # Check and report.
    rows = []
    for comp, item in tqdm(machines.items(), desc="Kontrol"):
        fqdn = item["DnsHostName"] or f"{comp}.{ad_domain}"
        ip = name_to_ip.get(comp, "N/A")

        winrm_open = False
        rdp_open = False
        user_status = "Hostname not resolvable" if ip == "N/A" else "Unchecked"

        if ip != "N/A":
            winrm_open = tcp_up(ip, 5985, timeout)
            rdp_open = tcp_up(ip, 3389, timeout)

            if winrm_open:
                user_status = winrm_quser(ip, args.TargetUser, timeout)
            else:
                user_status = "WinRM closed/unreachable"

        rows.append({
            "ComputerName": comp,
            "FQDN": fqdn,
            "IPAddress": ip,
            "WinRMPortOpen": winrm_open,
            "RdpPortOpen": rdp_open,
            "TargetUser": args.TargetUser,
            "UserSessionStatus": user_status,
            "CheckedAtUTC": datetime.datetime.now(UTC).isoformat(),
        })

    df = pd.DataFrame(rows, columns=[
        "ComputerName", "FQDN", "IPAddress",
        "WinRMPortOpen", "RdpPortOpen",
        "TargetUser", "UserSessionStatus", "CheckedAtUTC"
    ])

    out_dir = "./output"
    os.makedirs(out_dir, exist_ok=True)
    #out_file = f"{out_dir}/rdp_check_{datetime.datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}.csv"
    out_file = f"{out_dir}/rdp_check.csv"
    df.to_csv(out_file, index=False)
    print(f"Kaydedildi: {out_file}")


if __name__ == "__main__":
    main()
